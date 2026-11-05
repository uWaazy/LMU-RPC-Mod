"""
lmu/racecontrol.py - Driver Rating (DR), Safety Rating (SR) e Driver Badge para o LMU RPC Mod.

O QUE FOI COMPROVADO NO CODIGO (ver RELATORIO_RACECONTROL.md):
  * A Shared Memory do LMU (LMUVehicleScoring) NAO tem DR, SR nem badge. So tem `mSteamID`
    (SteamID do piloto, por carro). Por isso este modulo usa o SteamID como chave.
  * Os dados de DR/SR/badge vivem no backend RaceControl (Nakama) e so chegam ao cliente por
    um backend autenticado. O LMU Assister expoe um espelho em /api/v3 (ver RemoteProfileProvider),
    mas a descoberta da URL base exige um token de atestacao (App Check) que NAO e publico.

  * ATUALIZACAO (teste real do usuario, 31/10/2026): o proprio jogo entrega um ticket Steam em
    http://127.0.0.1:6397/rest/profile/getAuthSessionTicket. Esse ticket vira um token em
    https://raceos.gg/authenticate e POST /api/v1/players {"usernames":[...]} devolve
    driverRank / safetyRank / profile.badge. A consulta e por NOME DE USUARIO (nao por SteamID):
    na Shared Memory o mSteamID veio 0 em todos os carros, mas mDriverName vem preenchido.
    -> RaceOSProvider (opt-in). Endpoint NAO documentado oficialmente.

POR ISSO, as fontes sao "plugaveis" e NENHUMA inventa dados:
  * RaceOSProvider        -> fonte automatica (jogador local e, opcionalmente, pilotos da sessao).
  * ManualProvider        -> valores que o proprio usuario digitou no config.json (marcados "manual").
  * LocalRestProvider     -> URLs do REST local do jogo que o USUARIO configurar (padrao: nenhuma).
  * RemoteProfileProvider -> backend compativel com o schema do Assister; desligado por padrao
                             (precisa de base_url + token fornecidos/autorizados pelo dono do backend).

Regras de qualidade:
  * Falha de rede/autenticacao NUNCA troca um dado valido por valor padrao (mantem o ultimo valido).
  * Cache com TTL configuravel + cache negativo curto + backoff exponencial em erros.
  * Nada de senha Steam. O token remoto e lido de variavel de ambiente (nao fica no config.json).
"""

from __future__ import annotations

import logging
import json
import os
import random
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional

logger = logging.getLogger("LMU_RPC.racecontrol")

# --------------------------------------------------------------------------------------
# Badges oficiais do jogo (independentes do Safety Rating!)
# --------------------------------------------------------------------------------------

BADGE_ROOKIE = "rookie"
BADGE_GOOD = "good_driver"
BADGE_TRUSTED = "trusted_driver"
BADGE_WARNING = "warning"
BADGE_PROBATION = "probation"

OFFICIAL_BADGES = (BADGE_ROOKIE, BADGE_GOOD, BADGE_TRUSTED, BADGE_WARNING, BADGE_PROBATION)

BADGE_LABELS = {
    BADGE_ROOKIE: "Rookie",
    BADGE_GOOD: "Good Driver",
    BADGE_TRUSTED: "Trusted Driver",
    BADGE_WARNING: "Warning",
    BADGE_PROBATION: "Probation",
}

# Chaves de imagem do Discord que JA existem no seu app (ver VALID_BADGES antigo do lmu/app.py).
# ATENCAO: o mapeamento nome-oficial -> arte e uma SUPOSICAO (nao ha como verificar a arte pelo
# codigo). Ajuste em config.json -> "racecontrol" -> "badge_assets" se algum estiver trocado.
DEFAULT_BADGE_ASSETS = {
    BADGE_ROOKIE: "sr-rookie",
    BADGE_GOOD: "sr-clean",
    BADGE_TRUSTED: "sr-saint",
    BADGE_WARNING: "sr-warning",
    BADGE_PROBATION: "sr-probation",
}

# Badges que ja existem nos seus assets alem dos 5 oficiais. Passam direto (slug = asset).
EXTRA_BADGE_SLUGS = frozenset({
    "content-creator", "early-access", "irl-driver", "s397", "test-driver", "sr-danger", "sr-noob",
})

LOCAL_KEY = "local"      # chave do jogador local quando o nome ainda nao e conhecido
NAME_PREFIX = "name:"    # chave de um piloto identificado pelo nome (SteamID indisponivel)


def badge_label(badge: str) -> str:
    return BADGE_LABELS.get(badge) or str(badge).replace("-", " ").title()


# Ordem importa: padroes mais especificos primeiro.
_BADGE_PATTERNS = (
    (BADGE_PROBATION, re.compile(r"probation")),
    (BADGE_WARNING, re.compile(r"warn")),
    (BADGE_TRUSTED, re.compile(r"trust")),
    (BADGE_GOOD, re.compile(r"good|clean")),
    (BADGE_ROOKIE, re.compile(r"rookie|novice|newbie")),
)


def normalize_badge(raw: Any) -> Optional[str]:
    """Converte o texto/URL de badge devolvido por uma fonte para um dos 5 badges oficiais.

    Retorna None (e NAO um padrao) se nao reconhecer. Aceita nome ("Good Driver"),
    slug ("good_driver", "sr-clean") ou URL de imagem (".../badge_trusted.png").
    """
    if raw is None:
        return None
    if isinstance(raw, dict):
        for key in ("badge", "name", "label", "id", "key"):
            if raw.get(key):
                found = normalize_badge(raw[key])
                if found:
                    return found
        return None
    text = str(raw).strip().lower()
    if not text:
        return None
    text = text.rsplit("/", 1)[-1]
    text = re.sub(r"\.(png|jpe?g|webp|svg)$", "", text)
    slug = re.sub(r"[\s_]+", "-", text)
    if slug in EXTRA_BADGE_SLUGS:
        return slug
    text = re.sub(r"[\s_\-]+", " ", text)
    if text in {"saint", "sr saint"}:  # slug legado do asset antigo
        return BADGE_TRUSTED
    for badge, pattern in _BADGE_PATTERNS:
        if pattern.search(text):
            return badge
    return None


# --------------------------------------------------------------------------------------
# Ratings (DR / SR)
# --------------------------------------------------------------------------------------

_RANK_WORDS = {"bronze": "B", "silver": "S", "gold": "G", "platinum": "P"}
_RANK_LETTERS = ("B", "S", "G", "P")


@dataclass(frozen=True)
class Rating:
    """Rating normalizado. rank in {B,S,G,P,Pro}; tier inteiro; progress em % (0..100) ou None."""

    rank: str
    tier: int
    progress: Optional[float] = None
    value: Optional[float] = None  # elo/rating numerico bruto, se a fonte mandar

    def short(self, with_progress: bool = True) -> str:
        text = "Pro" if self.rank == "Pro" else f"{self.rank}{self.tier}"
        if with_progress and self.progress is not None:
            text += f" ({self.progress:g}%)"
        return text


def _to_progress(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):  # RaceOS: progress e int = porcentagem (confirmado no teste real)
        return float(value) if 0 <= value <= 100 else None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    if 0.0 <= number <= 1.0:
        number *= 100.0  # fracao -> %
    if not 0.0 <= number <= 100.0:
        return None
    return round(number, 1)


def _clean_rank_letter(rank: Any) -> Optional[str]:
    if rank is None:
        return None
    text = str(rank).strip().lower()
    if not text:
        return None
    if text == "pro":
        return "Pro"
    for word, letter in _RANK_WORDS.items():
        if text.startswith(word):
            return letter
    letter = text[0].upper()
    return letter if letter in _RANK_LETTERS else None


def parse_rating_string(text: Any) -> Optional[Rating]:
    """Interpreta textos como 'S1 (20%)', 'Gold G1 (10%)', 'Silver 2', 'P3'. None se invalido."""
    if text is None:
        return None
    raw = str(text).strip()
    if not raw:
        return None
    progress = None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", raw)
    if m:
        progress = _to_progress(float(m.group(1).replace(",", ".")))
        raw = raw[: m.start()] + raw[m.end():]
    raw = raw.replace("(", " ").replace(")", " ").strip()
    letter = None
    low = raw.lower()
    if re.match(r"pro\b", low):
        return Rating("Pro", 0, progress)
    for word, let in _RANK_WORDS.items():
        if word in low:
            letter = let
            break
    if letter is None:
        m2 = re.search(r"\b([bsgp])(?=\s*\d|\b)", low)
        if m2:
            letter = m2.group(1).upper()
    digits = re.findall(r"\d", raw)
    if letter is None or not digits:
        return None
    return Rating(letter, int(digits[-1]), progress)


def parse_rating(payload: Any) -> Optional[Rating]:
    """Interpreta um RatingDto do Assister: {rank, tier, progress, elo, rating, label}.

    Tambem aceita string. Retorna None quando nao ha dado utilizavel (nunca um padrao).
    """
    if payload is None:
        return None
    if isinstance(payload, str):
        return parse_rating_string(payload)
    if not isinstance(payload, dict):
        return None
    letter = _clean_rank_letter(payload.get("rank"))
    tier = payload.get("tier")
    try:
        tier = int(tier) if tier is not None else None
    except (TypeError, ValueError):
        tier = None
    if letter == "Pro" and tier is None:
        tier = 0
    if letter is None or tier is None or not 0 <= tier <= 9:
        # tenta o texto pronto ("label") antes de desistir
        return parse_rating_string(payload.get("label"))
    value = payload.get("elo") if payload.get("elo") is not None else payload.get("rating")
    try:
        value = float(value) if value is not None else None
    except (TypeError, ValueError):
        value = None
    return Rating(letter, tier, _to_progress(payload.get("progress")), value)


# --------------------------------------------------------------------------------------
# Perfil de piloto
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class DriverProfile:
    steam_id: str = ""
    name: str = ""
    dr: Optional[Rating] = None
    sr: Optional[Rating] = None
    badge: Optional[str] = None  # um de OFFICIAL_BADGES
    source: str = ""  # "manual" | "local_rest" | "remote"
    fetched_at: float = field(default_factory=time.time)

    @property
    def has_data(self) -> bool:
        return bool(self.dr or self.sr or self.badge)

    def merged_over(self, older: Optional["DriverProfile"]) -> "DriverProfile":
        """Preenche campos ausentes com os do perfil anterior (nunca apaga dado valido)."""
        if older is None:
            return self
        return DriverProfile(
            steam_id=self.steam_id or older.steam_id,
            name=self.name or older.name,
            dr=self.dr or older.dr,
            sr=self.sr or older.sr,
            badge=self.badge or older.badge,
            source=self.source or older.source,
            fetched_at=self.fetched_at,
        )


def parse_profile(payload: Any, steam_id: str = "", source: str = "") -> Optional[DriverProfile]:
    """Interpreta o JSON de perfil (schema SteamProfile/PublicUserDto do Assister).

    Chaves lidas (todas confirmadas em ProfileDtos.kt / PublicUserDtos.kt):
      name | display_name | username, driver_rating, safety_rating, badge, badge_url, badges[]
    Retorna None se o JSON nao tiver nenhum dado util.
    """
    if not isinstance(payload, dict):
        return None
    name = str(payload.get("name") or payload.get("display_name") or payload.get("username") or "")
    dr = parse_rating(payload.get("driver_rating"))
    sr = parse_rating(payload.get("safety_rating"))
    badge = normalize_badge(payload.get("badge")) or normalize_badge(payload.get("badge_url"))
    if badge is None:
        for item in payload.get("badges") or []:
            badge = normalize_badge(item)
            if badge:
                break
    profile = DriverProfile(steam_id=str(steam_id or ""), name=name, dr=dr, sr=sr, badge=badge, source=source)
    return profile if profile.has_data else None


# --------------------------------------------------------------------------------------
# Cache (TTL positivo + negativo), com relogio injetavel para teste
# --------------------------------------------------------------------------------------


class ProfileCache:
    def __init__(self, ttl: float = 900.0, negative_ttl: float = 120.0, clock: Callable[[], float] = time.time):
        self.ttl = max(0.0, float(ttl))
        self.negative_ttl = max(0.0, float(negative_ttl))
        self._clock = clock
        self._items: Dict[str, tuple] = {}  # key -> (stored_at, profile|None)
        self._lock = threading.Lock()

    def get(self, key: str, ttl: Optional[float] = None):
        """Retorna (found, profile, fresh). 'fresh' False = expirado mas ainda util como reserva."""
        with self._lock:
            entry = self._items.get(key)
        if entry is None:
            return False, None, False
        stored_at, profile = entry
        ttl = (self.ttl if ttl is None else ttl) if profile is not None else self.negative_ttl
        return True, profile, (self._clock() - stored_at) < ttl

    def put(self, key: str, profile: Optional[DriverProfile]) -> None:
        with self._lock:
            self._items[key] = (self._clock(), profile)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._items.pop(key, None)

    def last_good(self, key: str) -> Optional[DriverProfile]:
        with self._lock:
            entry = self._items.get(key)
        return entry[1] if entry else None

    # -- persistencia: evita consultar de novo ao reabrir o app dentro do TTL --
    def save(self, path: str, keys: Iterable[str]) -> None:
        data = {}
        with self._lock:
            for key in keys:
                entry = self._items.get(key)
                if entry and entry[1] is not None and entry[1].has_data:
                    data[key] = {"stored_at": entry[0], "profile": profile_to_dict(entry[1])}
        try:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            os.replace(tmp, path)
        except OSError:
            logger.debug("[racecontrol] nao foi possivel gravar o cache em disco", exc_info=True)

    def load(self, path: str, max_age: float = 86400.0) -> int:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return 0
        loaded, now = 0, self._clock()
        for key, item in (data or {}).items():
            try:
                stored_at = float(item["stored_at"])
                profile = profile_from_dict(item["profile"])
            except (KeyError, TypeError, ValueError):
                continue
            if profile is None or not (0 <= now - stored_at <= max_age):
                continue
            with self._lock:
                self._items.setdefault(key, (stored_at, profile))
            loaded += 1
        return loaded


def _rating_to_dict(r: Optional[Rating]):
    return None if r is None else {"rank": r.rank, "tier": r.tier, "progress": r.progress, "value": r.value}


def _rating_from_dict(d: Any) -> Optional[Rating]:
    if not isinstance(d, dict) or "rank" not in d or "tier" not in d:
        return None
    return Rating(str(d["rank"]), int(d["tier"]), d.get("progress"), d.get("value"))


def profile_to_dict(p: DriverProfile) -> Dict[str, Any]:
    return {"steam_id": p.steam_id, "name": p.name, "dr": _rating_to_dict(p.dr), "sr": _rating_to_dict(p.sr),
            "badge": p.badge, "source": p.source, "fetched_at": p.fetched_at}


def profile_from_dict(d: Any) -> Optional[DriverProfile]:
    if not isinstance(d, dict):
        return None
    prof = DriverProfile(steam_id=str(d.get("steam_id") or ""), name=str(d.get("name") or ""),
                         dr=_rating_from_dict(d.get("dr")), sr=_rating_from_dict(d.get("sr")),
                         badge=d.get("badge"), source=str(d.get("source") or ""),
                         fetched_at=float(d.get("fetched_at") or 0.0))
    return prof if prof.has_data else None


# --------------------------------------------------------------------------------------
# Provedores
# --------------------------------------------------------------------------------------


class ProviderUnavailable(Exception):
    """Falha transitoria (rede, 5xx, timeout). O servico mantem o ultimo dado valido."""


class ProviderAuthError(ProviderUnavailable):
    """401/403: credencial ausente/invalida. Sem retry agressivo."""


class ProfileProvider:
    name = "base"
    supports_batch = False  # True = o servico chama fetch_many(chaves) uma vez so

    def fetch(self, steam_id: str) -> Optional[DriverProfile]:  # pragma: no cover - interface
        raise NotImplementedError

    def fetch_many(self, keys: List[str]) -> Dict[str, Optional[DriverProfile]]:
        return {k: self.fetch(k) for k in keys}


class ManualProvider(ProfileProvider):
    """Valores digitados pelo usuario (config.json: dr, sr, badge). Apenas para o jogador local."""

    name = "manual"

    def __init__(self, dr: Any = "", sr: Any = "", badge: Any = ""):
        self.update(dr, sr, badge)

    def update(self, dr: Any = "", sr: Any = "", badge: Any = "") -> None:
        self._dr = parse_rating_string(dr)
        self._sr = parse_rating_string(sr)
        self._badge = normalize_badge(badge)
        bad = [n for n, raw, parsed in (("dr", dr, self._dr), ("sr", sr, self._sr), ("badge", badge, self._badge))
               if raw and not parsed]
        if bad:
            logger.warning("Valores manuais invalidos/ignorados no config: %s", ", ".join(bad))

    def fetch(self, steam_id: str) -> Optional[DriverProfile]:
        profile = DriverProfile(steam_id=str(steam_id or ""), dr=self._dr, sr=self._sr, badge=self._badge, source=self.name)
        return profile if profile.has_data else None


class _HttpProvider(ProfileProvider):
    timeout = 3.0

    def __init__(self, session: Any = None):
        if session is None:
            import requests  # ja esta no requirements.txt

            session = requests.Session()
        self._session = session

    def _get_json(self, url: str, headers: Optional[Dict[str, str]] = None) -> Any:
        try:
            resp = self._session.get(url, headers=headers or {}, timeout=self.timeout)
        except Exception as exc:  # timeout, DNS, conexao recusada...
            raise ProviderUnavailable(f"{type(exc).__name__}: {exc}") from exc
        status = getattr(resp, "status_code", 0)
        if status == 404:
            return None
        if status in (401, 403):
            raise ProviderAuthError(f"HTTP {status}")
        if not 200 <= status < 300:
            raise ProviderUnavailable(f"HTTP {status}")
        try:
            return resp.json()
        except ValueError as exc:
            raise ProviderUnavailable(f"JSON invalido: {exc}") from exc


class LocalRestProvider(_HttpProvider):
    """Le o REST local do jogo SOMENTE nas URLs que o usuario configurar.

    NENHUMA URL vem por padrao: os caminhos que o codigo antigo tentava (/rest/profile,
    /rest/player, /rest/racecontrol/profile) nao existem em nenhum projeto de referencia.
    Use `python -m lmu.racecontrol --probe-local` para descobrir o que o SEU jogo responde.
    """

    name = "local_rest"
    timeout = 1.0

    def __init__(self, urls: Iterable[str] = (), session: Any = None):
        super().__init__(session)
        self.urls = [u for u in (urls or []) if isinstance(u, str) and u.startswith(("http://127.0.0.1", "http://localhost"))]

    def fetch(self, steam_id: str) -> Optional[DriverProfile]:
        last_error: Optional[Exception] = None
        for url in self.urls:
            try:
                profile = parse_profile(self._get_json(url), steam_id, self.name)
            except ProviderUnavailable as exc:
                last_error = exc
                continue
            if profile:
                return profile
        if last_error and len(self.urls) and not isinstance(last_error, ProviderAuthError):
            raise last_error
        return None


class RemoteProfileProvider(_HttpProvider):
    """Cliente do backend compativel com o Assister (schema confirmado no codigo-fonte).

    Rotas (Apis.kt): GET {base}/users/{uid}  ->  perfil publico (SteamProfile).
    Auth (SteamBackendApi.kt): "Authorization: Bearer <token>" quando exigido.

    ATENCAO - NAO VERIFICADO: `uid` e o id do backend (Nakama), nao necessariamente o SteamID.
    O codigo do Assister nao prova que /users/{steamid} resolve. Se 404, o resultado e "sem dado"
    (cache negativo), nunca um valor inventado.
    Desligado por padrao: exige remote_base_url + token fornecidos/autorizados pelo dono do backend.
    """

    name = "remote"

    def __init__(self, base_url: str, token_getter: Callable[[], Optional[str]] = lambda: None, session: Any = None):
        super().__init__(session)
        self.base_url = (base_url or "").rstrip("/")
        self._token_getter = token_getter

    @property
    def configured(self) -> bool:
        return self.base_url.startswith("https://")

    def fetch(self, steam_id: str) -> Optional[DriverProfile]:
        if not self.configured:
            return None
        from urllib.parse import quote

        headers = {}
        token = self._token_getter()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        payload = self._get_json(f"{self.base_url}/users/{quote(str(steam_id), safe='')}", headers)
        return parse_profile(payload, steam_id, self.name)


# --------------------------------------------------------------------------------------
# RaceOS (backend do RaceControl usado pelo proprio jogo) - OPT-IN
# --------------------------------------------------------------------------------------

RACEOS_LOCAL = "http://127.0.0.1:6397"
RACEOS_TICKET_ROUTE = "/rest/profile/getAuthSessionTicket"       # rota REAL do REST local (confirmada no seu teste)
RACEOS_PROFILE_ROUTE = "/rest/profile/profileInfo/getProfileInfo"  # idem: devolve nick/name do jogador local
RACEOS_HOST_RULE = re.compile(r"^[a-z0-9.-]*raceos[a-z0-9.-]*$")
_LONG_TOKEN = re.compile(r"[A-Za-z0-9_\-+/=.]{40,}")
_warned_badges: set = set()


def _redact(text: Any) -> str:
    """Remove qualquer sequencia longa (ticket/JWT) antes de logar ou mostrar."""
    return _LONG_TOKEN.sub("<redigido>", str(text or "")[:200])


RACEOS_MAX_PER_HOUR = 12          # teto local de chamadas ao servidor remoto por hora
RACEOS_PAUSE_RATE_LIMIT = 900.0   # pausa apos HTTP 429 (dobra a cada reincidencia, ate 4 h)
RACEOS_PAUSE_SERVER_ERROR = 300.0  # pausa apos HTTP 5xx
RACEOS_PAUSE_AUTH = 21600.0       # pausa (6 h) se a autenticacao for recusada


def _urllib_http(method: str, url: str, headers: Optional[Dict[str, str]] = None, body: Any = None, timeout: float = 10):
    import urllib.error
    import urllib.request

    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json", "User-Agent": "LMU-RPC-Mod", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except Exception as exc:  # DNS, timeout, conexao recusada...
        return None, type(exc).__name__


def _extract_ticket(status: Any, text: str) -> Optional[str]:
    import json

    if status != 200 or not (text or "").strip():
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return text.strip().strip('"') or None
    if isinstance(data, str):
        return data or None
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str) and re.search(r"ticket|token", key, re.IGNORECASE):
                return value
    return None


def _expiry_epoch(text: Any, now: float) -> float:
    from datetime import datetime, timezone

    try:
        stamp = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return stamp.timestamp()
    except (ValueError, TypeError):
        return now + 600.0


def parse_raceos_record(record: Any, source: str = "raceos") -> Optional[DriverProfile]:
    """Interpreta um registro de /api/v1/players (formato confirmado no seu teste):
    driverRank{elo,rank,tier,progress}, safetyRank{rank,tier,rating,progress}, profile{badge,...}.
    """
    if not isinstance(record, dict):
        return None
    profile = record.get("profile") if isinstance(record.get("profile"), dict) else {}
    raw_badge = profile.get("badge")
    badge = normalize_badge(raw_badge)
    if raw_badge and badge is None and raw_badge not in _warned_badges:
        _warned_badges.add(raw_badge)
        logger.warning("[raceos] badge desconhecido (ignorado): %r. Me envie este valor para mapear.", raw_badge)
    result = DriverProfile(
        name=str(record.get("name") or record.get("username") or ""),
        dr=parse_rating(record.get("driverRank")),
        sr=parse_rating(record.get("safetyRank")),
        badge=badge,
        source=source,
    )
    return result if result.has_data else None


class RaceOSProvider(ProfileProvider):
    """Consulta DR/SR/badge no RaceOS usando o ticket de login Steam que o PROPRIO JOGO gera.

    Fluxo (comprovado no teste real): ticket local -> POST https://{host}/authenticate ->
    accessToken -> POST https://{host}/api/v1/players {"usernames": [...]} (header Game-Authorization).
    Chaves aceitas: LOCAL_KEY (nome vem do REST local) e "name:<usuario>" (nome exato, com #1234 se houver).
    SteamID puro NAO e suportado por este fluxo.

    Seguranca: o host precisa conter "raceos" e e sempre https; ticket e token nunca sao logados.
    NAO e uma API publica documentada: pode mudar ou limitar uso sem aviso. Por isso e opt-in.
    """

    name = "raceos"
    supports_batch = True

    def __init__(self, host: str = "raceos.gg", http: Optional[Callable] = None,
                 clock: Callable[[], float] = time.time, chunk_size: int = 20, local_url: str = RACEOS_LOCAL,
                 max_per_hour: int = RACEOS_MAX_PER_HOUR):
        host = (host or "").strip().lower()
        if not RACEOS_HOST_RULE.match(host):
            raise ValueError("host do RaceOS invalido: precisa conter 'raceos' (letras, numeros, pontos e hifens)")
        self.host = host
        self._http = http or _urllib_http
        self._clock = clock
        self.chunk_size = max(1, int(chunk_size))
        self._local_url = local_url.rstrip("/")
        self._token: Optional[str] = None
        self._expires = 0.0
        self._local_hint = ""
        self._lock = threading.Lock()
        self.max_per_hour = max(1, int(max_per_hour))
        self._calls: List[float] = []
        self._pause_until = 0.0
        self._strikes = 0

    # -- protecao contra excesso de requisicoes (so o servidor remoto conta; o jogo local nao) --
    def _pause(self, seconds: float, why: str) -> None:
        self._pause_until = max(self._pause_until, self._clock() + seconds)
        logger.warning("[raceos] pausando consultas por %d min (%s)", int(seconds // 60), why)

    def _guard(self) -> None:
        now = self._clock()
        if now < self._pause_until:
            raise ProviderUnavailable(f"RaceOS em pausa por mais {int(self._pause_until - now)} s")

    def _remote(self, method: str, url: str, headers: Optional[Dict[str, str]], body: Any, timeout: float):
        self._guard()
        now = self._clock()
        with self._lock:
            self._calls = [c for c in self._calls if now - c < 3600.0]
            if len(self._calls) >= self.max_per_hour:
                raise ProviderUnavailable("limite local de consultas por hora atingido")
            self._calls.append(now)
        status, text = self._http(method, url, headers, body, timeout)
        if status == 429:
            self._strikes += 1
            self._pause(min(14400.0, RACEOS_PAUSE_RATE_LIMIT * 2 ** (self._strikes - 1)), "HTTP 429")
        elif isinstance(status, int) and status >= 500:
            self._pause(RACEOS_PAUSE_SERVER_ERROR, f"HTTP {status}")
        elif status in (401, 403) and url.endswith("/authenticate"):
            self._pause(RACEOS_PAUSE_AUTH, f"autenticacao recusada (HTTP {status})")
        elif status == 200:
            self._strikes = 0
        return status, text

    def set_local_name(self, name: str) -> None:
        self._local_hint = (name or "").strip()

    # -- jogo local --
    def _local_names(self) -> List[str]:
        import json

        names = [self._local_hint] if self._local_hint else []
        status, text = self._http("GET", self._local_url + RACEOS_PROFILE_ROUTE, None, None, 4)
        if status == 200:
            try:
                info = json.loads(text)
                names += [str(info[k]).strip() for k in ("nick", "name") if isinstance(info, dict) and info.get(k)]
            except ValueError:
                pass
        unique: List[str] = []
        for n in names:
            if n and n not in unique:
                unique.append(n)
        if not unique and status != 200:
            # jogo fechado/REST local fora do ar: e FALHA (mantem o ultimo valor e faz backoff), nao "sem dado"
            raise ProviderUnavailable(f"REST local do jogo nao respondeu (status {status}); o LMU esta aberto?")
        return unique

    def _authenticate(self, force: bool = False) -> str:
        import json

        with self._lock:
            if not force and self._token and self._clock() < self._expires - 120:
                return self._token
        status, text = self._http("GET", self._local_url + RACEOS_TICKET_ROUTE, None, None, 6)
        ticket = _extract_ticket(status, text)
        if not ticket:
            raise ProviderUnavailable(f"o jogo nao entregou o ticket (status {status}); o LMU esta aberto?")
        status, text = self._remote("POST", f"https://{self.host}/authenticate", None,
                                    {"token": ticket, "game": "lmu", "platform": "steam"}, 10)
        if status in (401, 403):
            raise ProviderAuthError(f"authenticate HTTP {status}")
        try:
            data = json.loads(text)
            token = data.get("accessToken") if isinstance(data, dict) else None
        except ValueError:
            data, token = {}, None
        if status != 200 or not token:
            raise ProviderUnavailable(f"authenticate falhou (status {status}): {_redact(text)}")
        with self._lock:
            self._token = token
            self._expires = _expiry_epoch(data.get("expiresAt"), self._clock())
        return token

    def _post_players(self, usernames: List[str]) -> List[Dict[str, Any]]:
        import json

        status, text = None, ""
        for attempt in range(2):
            token = self._authenticate(force=attempt == 1)
            status, text = self._remote("POST", f"https://{self.host}/api/v1/players",
                                        {"Game-Authorization": token}, {"usernames": usernames}, 10)
            if status == 401 and attempt == 0:
                with self._lock:
                    self._token = None
                continue
            break
        if status in (401, 403):
            raise ProviderAuthError(f"players HTTP {status}")
        if status != 200:
            raise ProviderUnavailable(f"players HTTP {status}: {_redact(text)}")
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise ProviderUnavailable("resposta que nao e JSON") from exc
        if isinstance(data, dict):
            data = data.get("players") or data.get("data") or [data]
        return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []

    # -- interface --
    def fetch(self, key: str) -> Optional[DriverProfile]:
        return self.fetch_many([key]).get(key)

    def fetch_many(self, keys: List[str]) -> Dict[str, Optional[DriverProfile]]:
        self._guard()  # em pausa: nem chega a consultar o jogo
        key_names: Dict[str, List[str]] = {}
        for key in keys:
            if key == LOCAL_KEY:
                key_names[key] = self._local_names()
            elif key.startswith(NAME_PREFIX) and key[len(NAME_PREFIX):].strip():
                key_names[key] = [key[len(NAME_PREFIX):].strip()]
            else:
                key_names[key] = []  # SteamID puro: nao suportado por este fluxo
        usernames: List[str] = []
        for names in key_names.values():
            for n in names:
                if n.casefold() not in {u.casefold() for u in usernames}:
                    usernames.append(n)
        if not usernames:
            return {k: None for k in keys}
        records: List[Dict[str, Any]] = []
        for i in range(0, len(usernames), self.chunk_size):
            records.extend(self._post_players(usernames[i:i + self.chunk_size]))
        by_name: Dict[str, DriverProfile] = {}
        for rec in records:
            parsed = parse_raceos_record(rec, self.name)
            if not parsed:
                continue
            for field_name in ("username", "name"):
                cf = str(rec.get(field_name) or "").casefold()
                if cf:
                    by_name.setdefault(cf, parsed)
        out: Dict[str, Optional[DriverProfile]] = {}
        for key, names in key_names.items():
            out[key] = next((by_name[n.casefold()] for n in names if n.casefold() in by_name), None)
        return out



# --------------------------------------------------------------------------------------
# Jogadores da sessao (Shared Memory)
# --------------------------------------------------------------------------------------


def _decode(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw).split(b"\x00")[0].decode("utf-8", errors="ignore").strip()
    return str(raw).strip()


def extract_session_players(scoring: Any) -> List[Dict[str, Any]]:
    """Lista os carros da sessao com SteamID. So le campos que EXISTEM em LMUVehicleScoring.

    Cada item: {steam_id (str, '' se 0), name, is_player, control, slot_id}.
    SteamID 0 = desconhecido (IA ou nao preenchido) -> steam_id vazio.
    """
    players: List[Dict[str, Any]] = []
    try:
        total = int(scoring.scoringInfo.mNumVehicles)
    except Exception:
        return players
    for i in range(total):
        try:
            veh = scoring.vehScoringInfo[i]
            sid = int(getattr(veh, "mSteamID", 0) or 0)
            players.append(
                {
                    "steam_id": str(sid) if sid > 0 else "",
                    "name": _decode(getattr(veh, "mDriverName", b"")),
                    "is_player": bool(getattr(veh, "mIsPlayer", False)),
                    "control": int(getattr(veh, "mControl", -1)),
                    "slot_id": int(getattr(veh, "mID", -1)),
                }
            )
            players[-1]["key"] = player_key(players[-1])
        except Exception as exc:
            logger.debug("Falha ao ler veiculo %s da sessao: %s", i, exc)
    return players


# --------------------------------------------------------------------------------------
# Servico (cache + thread de fundo + backoff + consulta em lote)
# --------------------------------------------------------------------------------------


def player_key(player: Dict[str, Any]) -> str:
    """Chave de identidade: SteamID quando existe; senao o nome (o mSteamID veio 0 no seu teste)."""
    if player.get("key"):
        return str(player["key"])
    if player.get("steam_id"):
        return str(player["steam_id"])
    name = str(player.get("name") or "").strip()
    return NAME_PREFIX + name if name else ""


class RaceControlService:
    """Orquestra provedores, cache e consultas em segundo plano. Thread-safe."""

    def __init__(
        self,
        providers: Optional[List[ProfileProvider]] = None,
        cache: Optional[ProfileCache] = None,
        clock: Callable[[], float] = time.time,
        run_async: bool = True,
        max_backoff: float = 600.0,
        prefetch_session: bool = True,
    ):
        self.providers = list(providers or [])
        self.cache = cache or ProfileCache()
        self._clock = clock
        self._run_async = run_async
        self._max_backoff = max_backoff
        self.prefetch_session = prefetch_session
        self._lock = threading.Lock()
        self._inflight: set = set()
        self._fail_count: Dict[str, int] = {}
        self._retry_at: Dict[str, float] = {}
        self.local_steam_id: str = ""
        self.local_key: str = LOCAL_KEY
        self.local_name: str = ""
        self.session_players: List[Dict[str, Any]] = []
        self.local_ttl: Optional[float] = None          # TTL proprio do jogador local (None = usa o do cache)
        self.watch_schedule: List[float] = []           # segundos apos o fim da corrida em que reconsultar
        self._watch: Dict[str, Dict[str, Any]] = {}
        self.on_change: List[Callable[[str, Optional[DriverProfile], DriverProfile], None]] = []
        self.jitter: float = 0.0                        # variacao (+-) nos passos da vigia, p/ nao sincronizar usuarios
        self.persist: Optional[Callable[[], None]] = None  # chamado apos um dado novo (grava cache em disco)

    # ---- consulta -------------------------------------------------------------------
    def get(self, key: str) -> Optional[DriverProfile]:
        """Melhor perfil conhecido (pode ser reserva expirada); agenda refresh em segundo plano se preciso."""
        key = str(key or "")
        self._tick_watches()
        found, profile, fresh = self.cache.get(key, self._ttl_for(key))
        if not (found and fresh):
            self._schedule_many([key])
        return self.cache.last_good(key)  # rele: se a consulta foi sincrona, ja devolve o valor novo

    def _is_local(self, key: str) -> bool:
        return key in (LOCAL_KEY, self.local_key) or (bool(self.local_steam_id) and key == self.local_steam_id)

    def _ttl_for(self, key: str) -> Optional[float]:
        return self.local_ttl if (self.local_ttl is not None and self._is_local(key)) else None

    def get_local(self) -> Optional[DriverProfile]:
        profile = self.get(self.local_key)
        if profile is None and self.local_key != LOCAL_KEY:
            profile = self.cache.last_good(LOCAL_KEY)  # evita "piscar" ao trocar de chave
        return profile

    def _applies(self, provider: ProfileProvider, key: str) -> bool:
        if provider.name == "manual":  # valores digitados valem so para o jogador local
            return key in ("", LOCAL_KEY, self.local_key, self.local_steam_id)
        return True

    def refresh(self, key: str) -> Optional[DriverProfile]:
        key = str(key or "")
        return self.refresh_many([key]).get(key)

    def refresh_many(self, keys: List[str]) -> Dict[str, Optional[DriverProfile]]:
        """Consulta sincrona (thread de fundo e testes). Provedores em lote recebem todas as chaves de uma vez."""
        keys = list(dict.fromkeys(str(k or "") for k in keys))
        merged: Dict[str, DriverProfile] = {}
        errors: Dict[str, int] = {k: 0 for k in keys}
        for provider in self.providers:
            applicable = [k for k in keys if self._applies(provider, k)]
            if not applicable:
                continue
            if getattr(provider, "supports_batch", False):
                self._query(provider, applicable, merged, errors, batch=True)
            else:
                for k in applicable:
                    self._query(provider, [k], merged, errors, batch=False)
        return {k: self._finish(k, merged.get(k), errors[k]) for k in keys}

    def _query(self, provider, keys, merged, errors, batch: bool) -> None:
        label = keys[0] or "local"
        try:
            got = provider.fetch_many(keys) if batch else {keys[0]: provider.fetch(keys[0])}
        except ProviderAuthError as exc:
            logger.warning("[%s] autenticacao recusada (%s). Sem novas tentativas ate expirar o backoff.", provider.name, exc)
        except ProviderUnavailable as exc:
            logger.info("[%s] indisponivel para %s: %s", provider.name, label, exc)
        except Exception:
            logger.exception("[%s] erro inesperado ao consultar %s", provider.name, label)
        else:
            for k, res in (got or {}).items():
                if res and res.has_data:
                    # provedores anteriores (automaticos) tem prioridade; os seguintes so preenchem lacunas
                    merged[k] = merged[k].merged_over(res) if k in merged else res
            return
        for k in keys:
            errors[k] += 1

    @staticmethod
    def _sig(profile: Optional[DriverProfile]):
        if profile is None:
            return (None, None, None)
        return (profile.dr.short() if profile.dr else None, profile.sr.short() if profile.sr else None, profile.badge)

    def _finish(self, key: str, merged: Optional[DriverProfile], errors: int) -> Optional[DriverProfile]:
        previous = self.cache.last_good(key)
        result: Optional[DriverProfile]
        if merged:
            # Sucesso: o dado novo SUBSTITUI o anterior (SR/DR podem cair e o badge pode sumir ou mudar).
            result = merged
            self.cache.put(key, merged)
            if self.persist is not None and self._is_local(key):
                try:
                    self.persist()
                except Exception:
                    logger.debug("[racecontrol] persist falhou", exc_info=True)
            self._fail_count.pop(key, None)
            self._retry_at.pop(key, None)
            logger.info("[racecontrol] %s: DR=%s SR=%s badge=%s (fonte=%s)", key or "local",
                        merged.dr.short() if merged.dr else None, merged.sr.short() if merged.sr else None,
                        merged.badge, merged.source)
            if previous is not None and self._sig(previous) != self._sig(merged):
                logger.info("[racecontrol] %s MUDOU: DR %s -> %s | SR %s -> %s | badge %s -> %s", key or "local",
                            *self._sig(previous)[:1], *self._sig(merged)[:1],
                            *self._sig(previous)[1:2], *self._sig(merged)[1:2],
                            *self._sig(previous)[2:], *self._sig(merged)[2:])
                for callback in list(self.on_change):
                    try:
                        callback(key, previous, merged)
                    except Exception:
                        logger.exception("callback on_change falhou")
        else:
            result = previous
            if errors:
                # Falha: preserva o ultimo valido (se existir) e aplica backoff. NAO grava "vazio".
                count = self._fail_count.get(key, 0) + 1
                self._fail_count[key] = count
                delay = min(self._max_backoff, (self.cache.negative_ttl or 30.0) * (2 ** (count - 1)))
                self._retry_at[key] = self._clock() + delay
            if previous is None:
                self.cache.put(key, None)  # cache negativo curto (sem dado / falha)
        self._settle_watch(key, result if merged else None)
        return result

    # ---- vigia pos-corrida ----------------------------------------------------------
    def start_watch(self, keys: List[str], reason: str = "") -> None:
        """Apos o fim de uma corrida o servidor atualiza DR/SR/badge com atraso desconhecido:
        reconsulta em intervalos crescentes (watch_schedule) ate o perfil mudar ou os passos acabarem."""
        if not self.watch_schedule:
            return
        now = self._clock()
        started = []
        with self._lock:
            for k in keys:
                if not k or k in self._watch:  # ja vigiando: mantem a linha de base original
                    continue
                self._watch[k] = {"baseline": self._sig(self.cache.last_good(k)), "started": now,
                                  "steps": [now + d * (1.0 + random.uniform(-self.jitter, self.jitter)) for d in self.watch_schedule],
                                  "tries": 0}
                started.append(k)
        if started:
            logger.info("[racecontrol] vigia pos-corrida iniciada (%s) para %d perfil(is); passos: %s s",
                        reason or "-", len(started), [int(x) for x in self.watch_schedule])

    def _tick_watches(self) -> None:
        if not self._watch:
            return
        now = self._clock()
        due: List[str] = []
        with self._lock:
            for k, w in self._watch.items():
                if w["steps"] and w["steps"][0] <= now:
                    while w["steps"] and w["steps"][0] <= now:  # nao dispara rajada se o loop ficou parado
                        w["steps"].pop(0)
                    w["tries"] += 1
                    due.append(k)
        if due:
            self._schedule_many(due, force=True)

    def _settle_watch(self, key: str, fresh_profile: Optional[DriverProfile]) -> None:
        with self._lock:
            w = self._watch.get(key)
            if not w:
                return
            elapsed = int(self._clock() - w["started"])
            if fresh_profile is not None and self._sig(fresh_profile) != w["baseline"]:
                del self._watch[key]
                logger.info("[racecontrol] %s: rating atualizado %ds apos o fim da corrida (%d consulta(s))", key, elapsed, w["tries"])
            elif not w["steps"]:
                del self._watch[key]
                logger.info("[racecontrol] %s: sem mudanca de rating apos %d consulta(s) em %ds", key, w["tries"], elapsed)

    def _schedule_many(self, keys: List[str], force: bool = False) -> None:
        if not self.providers:
            return
        todo: List[str] = []
        with self._lock:
            now = self._clock()
            for k in dict.fromkeys(keys):
                if k in self._inflight:
                    continue
                if force:
                    self._retry_at.pop(k, None)  # evento explicito (fim de corrida) ignora o backoff
                else:
                    if now < self._retry_at.get(k, 0.0):
                        continue
                    found, _, fresh = self.cache.get(k, self._ttl_for(k))
                    if found and fresh:
                        continue
                self._inflight.add(k)
                todo.append(k)
        if not todo:
            return

        def _job():
            try:
                self.refresh_many(todo)
            finally:
                with self._lock:
                    self._inflight.difference_update(todo)

        if not self._run_async:
            _job()
            return
        threading.Thread(target=_job, name="rc-lookup", daemon=True).start()

    # ---- sessao ---------------------------------------------------------------------
    def update_session(self, players: List[Dict[str, Any]]) -> None:
        """Recebe os jogadores da Shared Memory, descobre o jogador local e (opt-in) pre-carrega a sessao."""
        self._tick_watches()
        for p in players:
            p["key"] = player_key(p)
        self.session_players = players
        local = next((p for p in players if p.get("is_player")), None)
        if local:
            if local.get("steam_id") and local["steam_id"] != self.local_steam_id:
                logger.info("[racecontrol] SteamID local detectado na Shared Memory: %s", local["steam_id"])
            self.local_steam_id = local.get("steam_id") or self.local_steam_id
            if local.get("name") and local["name"] != self.local_name:
                self.local_name = local["name"]
                self.local_key = NAME_PREFIX + local["name"]
                for provider in self.providers:
                    if hasattr(provider, "set_local_name"):
                        provider.set_local_name(local["name"])
        if self.prefetch_session:
            remote = [p["key"] for p in players if p["key"] and not p.get("is_player") and p.get("control") == 2]
            self._schedule_many(remote[:64])

    def players_with_ratings(self) -> List[Dict[str, Any]]:
        out = []
        for p in self.session_players:
            key = p.get("key") or player_key(p)
            prof = self.cache.last_good(key) if key else None
            out.append({**p, "dr": prof.dr.short() if prof and prof.dr else None,
                        "sr": prof.sr.short() if prof and prof.sr else None,
                        "badge": prof.badge if prof else None})
        return out


# --------------------------------------------------------------------------------------
# Adaptador usado pelo lmu/app.py (mesma interface do antigo RaceControlProfile)
# --------------------------------------------------------------------------------------

MIN_LOCAL_REFRESH = 1800.0   # nunca reconsulta o jogador local em menos de 30 min
MAX_WATCH_STEPS = 4          # a vigia pos-corrida faz no maximo 4 consultas
MIN_WATCH_STEP = 10.0
LEAVE_TRIGGER_GAP = 600.0    # sair de uma corrida dispara a vigia no maximo a cada 10 min

DEFAULT_RACEOS_CONFIG = {"enabled": False, "host": "raceos.gg", "chunk_size": 20}
DEFAULT_RC_CONFIG = {
    "enabled": True,
    "cache_ttl_seconds": 900,
    "negative_ttl_seconds": 300,
    "session_lookup": False,      # opt-in: consultar TAMBEM os demais pilotos da sessao
    "local_refresh_seconds": 3600,  # reconsulta periodica SO do jogador local (minimo aplicado: 1800)
    "refresh_on_race_end": True,   # ao fim/abandono de uma corrida, vigia ate o rating mudar
    "post_race_schedule_seconds": [30, 90, 240, 600],  # no maximo 4 consultas (~16 min)
    "raceos": DEFAULT_RACEOS_CONFIG,
    "remote_base_url": "",
    "remote_token_env": "LMU_RC_TOKEN",
    "local_endpoints": [],
    "badge_assets": {},
}


def build_service(config: Optional[Dict[str, Any]] = None, session: Any = None, http: Optional[Callable] = None,
                  cache_file: str = "") -> RaceControlService:
    config = config or {}
    rc = {**DEFAULT_RC_CONFIG, **(config.get("racecontrol") or {})}
    raceos_cfg = {**DEFAULT_RACEOS_CONFIG, **(rc.get("raceos") or {})}
    providers: List[ProfileProvider] = []
    # Ordem = prioridade. Fontes automaticas primeiro; o manual so preenche o que faltar.
    if rc["enabled"]:
        if rc["local_endpoints"]:
            providers.append(LocalRestProvider(rc["local_endpoints"], session))
        # "auto_rating": true (chave usada no outro rascunho) tambem liga o RaceOS.
        if raceos_cfg["enabled"] or config.get("auto_rating"):
            try:
                providers.append(RaceOSProvider(raceos_cfg["host"], http=http, chunk_size=raceos_cfg["chunk_size"]))
                logger.info("[racecontrol] RaceOS ativo: o ticket de login Steam gerado pelo jogo sera enviado a %s", raceos_cfg["host"])
            except ValueError as exc:
                logger.error("[racecontrol] RaceOS desativado: %s", exc)
        remote = RemoteProfileProvider(rc["remote_base_url"], lambda: os.environ.get(rc["remote_token_env"] or ""), session)
        if remote.configured:
            providers.append(remote)
    providers.append(ManualProvider(config.get("dr", ""), config.get("sr", ""), config.get("badge", "")))
    cache = ProfileCache(rc["cache_ttl_seconds"], rc["negative_ttl_seconds"])
    service = RaceControlService(providers, cache, prefetch_session=bool(rc["session_lookup"]), max_backoff=3600.0)
    # Limites de seguranca valem mesmo para config.json antigos (valores menores sao ignorados)
    service.local_ttl = max(MIN_LOCAL_REFRESH, float(rc["local_refresh_seconds"]))
    service.jitter = 0.1
    if rc["refresh_on_race_end"]:
        steps = sorted(max(MIN_WATCH_STEP, float(x)) for x in (rc["post_race_schedule_seconds"] or []))
        service.watch_schedule = steps[:MAX_WATCH_STEPS]
    # Cache em disco (so com RaceOS ativo): reabrir o app nao gera nova consulta enquanto o dado estiver fresco
    if cache_file and any(p.name == "raceos" for p in providers):
        loaded = cache.load(cache_file)
        if loaded:
            logger.info("[racecontrol] %d perfil(is) carregado(s) do cache em disco (sem nova consulta)", loaded)
        service.persist = lambda: cache.save(cache_file, {service.local_key, LOCAL_KEY})
    configured_id = str(config.get("steamid") or "").strip()
    if configured_id.isdigit():
        service.local_steam_id = configured_id
    return service


class RaceControlProfile:
    """Fachada para o lmu/app.py. Substitui a antiga classe de mesmo nome (que lia campos
    inexistentes da Shared Memory e chamava URLs adivinhadas)."""

    def __init__(self, config: Optional[Dict[str, Any]] = None, service: Optional[RaceControlService] = None,
                 cache_file: str = ""):
        self.config = config or {}
        self.service = service or build_service(self.config, cache_file=cache_file)
        self._assets = {**DEFAULT_BADGE_ASSETS, **((self.config.get("racecontrol") or {}).get("badge_assets") or {})}
        self.lock = threading.Lock()
        self._last_session = ""
        self._last_phase = None
        self._last_leave_trigger = -1e9

    def _local(self) -> Optional[DriverProfile]:
        return self.service.get_local()

    @property
    def dr(self) -> str:
        p = self._local()
        return p.dr.short() if p and p.dr else ""

    @property
    def sr(self) -> str:
        p = self._local()
        return p.sr.short() if p and p.sr else ""

    @property
    def badge(self) -> str:
        p = self._local()
        return p.badge or "" if p else ""

    def get_badge_asset(self) -> str:
        p = self._local()
        if not p or not p.badge:
            return ""
        return self._assets.get(p.badge) or (p.badge if p.badge in EXTRA_BADGE_SLUGS else "")

    def get_rank_letter(self) -> str:
        """Letra do rank do DR real (B/S/G/P); '' se nao ha DR ou e 'Pro'."""
        p = self._local()
        rank = getattr(getattr(p, "dr", None), "rank", "") if p else ""
        return rank if rank in ("B", "S", "G", "P") else ""

    def get_tooltip(self) -> str:
        """Texto do small_text do Discord (max 128). Vazio se nao houver NENHUM dado real."""
        p = self._local()
        if not p:
            return ""
        parts = []
        if p.dr:
            parts.append(f"DR {p.dr.short()}")
        if p.sr:
            parts.append(f"SR {p.sr.short()}")
        if p.badge:
            parts.append(badge_label(p.badge))
        return " | ".join(parts)[:128]

    def update_from_config(self, config: Dict[str, Any]) -> None:
        self.config = config
        for provider in self.service.providers:
            if isinstance(provider, ManualProvider):
                provider.update(config.get("dr", ""), config.get("sr", ""), config.get("badge", ""))
        for key in {self.service.local_key, LOCAL_KEY, self.service.local_steam_id}:
            self.service.cache.invalidate(key)  # forca reconsulta

    def refresh_from_memory(self, result: Dict[str, Any]) -> None:
        """Recebe o dict do RF2Data.update(); atualiza o jogador local e os jogadores da sessao."""
        result = result or {}
        info = result.get("ranks") or {}
        players = info.get("players") or []
        if players:
            self.service.update_session(players)
        else:
            self.service.get_local()
        self._detect_race_end(result)

    def _detect_race_end(self, result: Dict[str, Any]) -> None:
        """Fase 8 = sessao encerrada (lmu_data.py). Tambem conta SAIR de uma corrida (abandono/menu)."""
        session, phase = str(result.get("session") or ""), result.get("game_phase")
        race_over = session == "race" and phase == 8 and self._last_phase != 8
        left_race = self._last_session == "race" and session != "race"
        self._last_session, self._last_phase = session, phase
        if left_race and not race_over:
            # pausa/carregamento no meio da corrida tambem parece "saiu": no maximo 1 disparo a cada 10 min
            now = self.service._clock()
            if now - self._last_leave_trigger < LEAVE_TRIGGER_GAP:
                return
            self._last_leave_trigger = now
        if not (race_over or left_race):
            return
        keys = [self.service.local_key]
        if self.service.prefetch_session:
            keys += [p["key"] for p in self.service.session_players
                     if p.get("key") and not p.get("is_player") and p.get("control") == 2]
        self.service.start_watch(keys, "fim da corrida" if race_over else "saiu da corrida")

    def refresh_from_api(self) -> None:
        """Mantido por compatibilidade: a consulta ocorre via cache/TTL no servico."""
        self.service.get_local()


# --------------------------------------------------------------------------------------
# Diagnostico de linha de comando
# --------------------------------------------------------------------------------------


def _cli(argv: List[str]) -> int:  # pragma: no cover - usa o jogo
    import json
    import sys

    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # raiz do projeto
    sys.path.append(os.path.join(here, "pyLMUSharedMemory"))
    if "--probe-local" in argv:
        import requests

        base = "http://localhost:6397"
        for path in ("/swagger/index.html", "/rest/sessions/getAllVehicles", "/rest/sessions/weather", "/rest/status"):
            try:
                r = requests.get(base + path, timeout=1.5)
                print(f"{r.status_code} {path} ({len(r.content)} bytes)")
            except Exception as exc:
                print(f"ERR {path}: {exc}")
        print("Procure no Swagger do jogo qualquer rota de perfil e a ponha em config.json -> racecontrol.local_endpoints")
        return 0
    if "--raceos" in argv:
        cfg = {}
        cfg_path = os.path.join(here, "config.json")
        if os.path.exists(cfg_path):
            cfg = json.load(open(cfg_path, encoding="utf-8"))
        host = {**DEFAULT_RACEOS_CONFIG, **((cfg.get("racecontrol") or {}).get("raceos") or {})}["host"]
        try:
            prov = RaceOSProvider(host)
        except ValueError as exc:
            print(exc)
            return 1
        try:
            names = prov._local_names()
        except ProviderUnavailable as exc:
            print("Erro:", exc)
            return 1
        print(f"Isto envia o ticket de login Steam que o jogo gera para voce a: {host}")
        print("Nomes que serao consultados:", names or "nenhum (o jogo esta aberto?)")
        if not names or input("Digite SIM para continuar: ").strip().upper() != "SIM":
            print("Cancelado.")
            return 0
        try:
            result = prov.fetch_many([LOCAL_KEY])[LOCAL_KEY]
        except ProviderUnavailable as exc:
            print("Erro:", exc)
            return 1
        if not result:
            print("O RaceOS respondeu, mas sem registro/rating para esses nomes.")
            return 0
        print(f"DR={result.dr.short() if result.dr else None}  SR={result.sr.short() if result.sr else None}  "
              f"badge={result.badge}  (valores brutos: DR {result.dr}, SR {result.sr})")
        return 0
    if "--list-endpoints" in argv:
        # Le a especificacao Swagger REAL do jogo. Confirmado no seu PC: o Swagger UI aponta para
        # http://localhost:6397/swagger-schema.json (definido em swagger-initializer.js).
        import requests

        base = "http://localhost:6397"
        candidates = [base + "/swagger-schema.json"]
        try:
            js = requests.get(base + "/swagger/swagger-initializer.js", timeout=5).text
            for m in re.findall(r"""["']((?:https?://[^"']+|/[^"']+)\.json)["']""", js):
                candidates.append(m if m.startswith("http") else base + m)
        except Exception as exc:
            print(f"(aviso) nao li swagger-initializer.js: {exc}")
        for path in ("/swagger/v1/swagger.json", "/swagger.json", "/openapi.json"):
            candidates.append(base + path)
        seen = set()
        for url in candidates:
            if url in seen:
                continue
            seen.add(url)
            try:
                r = requests.get(url, timeout=10)
                spec = r.json() if r.status_code == 200 else None
            except Exception:
                spec = None
            if isinstance(spec, dict) and isinstance(spec.get("paths"), dict):
                out = os.path.join(here, "lmu_rest_routes.txt")
                lines = [f"{','.join(m.upper() for m in methods if m.lower() != 'parameters')}  {route}"
                         for route, methods in sorted(spec["paths"].items())]
                with open(out, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
                keys = ("profile", "player", "user", "driver", "rating", "safety", "badge", "racecontrol",
                        "steam", "account", "license", "career", "stat")
                hits = [l for l in lines if any(k in l.lower() for k in keys)]
                print(f"Especificacao: {url} ({len(lines)} rotas). Lista completa salva em: {out}")
                print(f"\nRotas candidatas ({len(hits)}):")
                print("\n".join(hits) if hits else "(nenhuma)")
                return 0
            print(f"-- {url}: sem especificacao")
        print("Nenhuma especificacao encontrada.")
        return 1
    if "--diagnose-shm" in argv:
        from pyLMUSharedMemory.lmu_data import SimInfo

        scoring = SimInfo().LMUData.scoring
        players = extract_session_players(scoring)
        with_id = sum(1 for p in players if p["steam_id"])
        print(f"{len(players)} carros, {with_id} com SteamID ({'OK' if with_id else 'NENHUM SteamID preenchido'})")
        print(json.dumps(players, indent=2, ensure_ascii=False))
        return 0
    if "--lookup" in argv:
        steam_id = argv[argv.index("--lookup") + 1]
        cfg = json.load(open(os.path.join(here, "config.json"), encoding="utf-8")) if os.path.exists(os.path.join(here, "config.json")) else {}
        svc = build_service(cfg)
        svc._run_async = False
        print(svc.refresh(steam_id))
        return 0
    print("Uso: python -m lmu.racecontrol [--raceos | --list-endpoints | --probe-local | --diagnose-shm | --lookup STEAMID]")
    return 1


if __name__ == "__main__":  # pragma: no cover
    import sys

    sys.exit(_cli(sys.argv[1:]))
