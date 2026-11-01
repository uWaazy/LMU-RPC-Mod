<div align="right">
  <a href="README.md">
    <img src="https://img.shields.io/badge/Read%20in-English-blue?style=for-the-badge" alt="Read in English">
  </a>
  <a href="README.es.md">
    <img src="https://img.shields.io/badge/Leer%20en-Espa%C3%B1ol-yellow?style=for-the-badge" alt="Leer en Español">
  </a>
</div>

# LMU RPC Mod

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Release](https://img.shields.io/github/v/release/uWaazy/LMU-RPC-Mod?style=for-the-badge&color=green)](https://github.com/uWaazy/LMU-RPC-Mod/releases)
[![Discord](https://img.shields.io/discord/1463577784394973392?style=for-the-badge&logo=discord&logoColor=white&label=Suporte)](https://discord.gg/cE6B2azY73)

**LMU RPC Mod** é uma aplicação independente que traz o **Discord Rich Presence** para o **Le Mans Ultimate**. Mostre aos seus amigos o que você está pilotando, onde, sua posição na classe e seu Driver Rating, com atualizações em tempo real e detecção automática.

![LMU RPC Banner](preview.png)

## 📸 Visualização (Previews)

Veja como seu status aparece no Discord em diferentes situações de jogo:

<p align="center">
  <img src="img/preview1.png" alt="Menu" width="32%">
  <img src="img/preview2.png" alt="Treino" width="32%">
  <img src="img/preview3.png" alt="Corrida" width="32%">
</p>

## 🎮 O que aparece

```
Le Mans Ultimate
⏱ 43:20 | P5/12 (20 de 34) | Online
Barcelona | Mercedes-AMG LMGT3 | Treino Livre
```

| Linha | Conteúdo |
| :--- | :--- |
| 1 | Tempo restante (ou volta/fase) · **posição na sua classe** / carros da sua classe · `(carros na sessão de vagas)` só online · modo (Online / Fim de Semana) |
| 2 | Pista · Carro · Sessão (Treino, Qualificação, Corrida...) |
| Imagem grande | Alterna **carro (10 s)** e **pista (5 s)**. Pistas sem imagem ficam no carro |
| Ícone pequeno | Seu **Driver Badge**. Passe o mouse para ver `DR S1 (30%) \| SR G1 (10%) \| Good Driver` |

## 🛡️ Driver Rating, Safety Rating e Badges

O ícone pequeno na imagem é o seu **Driver Contact Badge**, e o tooltip mostra seu **DR** (Driver Rating) e **SR** (Safety Rating) como *rank + tier (progresso %)*, ex.: `S1 (30%)` = Prata, tier 1, 30% de progresso.

Esses valores **não** existem na memória compartilhada do jogo, então o mod nunca inventa nem estima nada. Eles vêm do ticket de login do próprio jogo e do serviço comunitário **RaceOS** (`raceos.gg`). É uma API não oficial e não documentada.

* **Opt-in:** desligado até você definir `racecontrol.raceos.enabled` como `true` no `config.json`. Ao ativar, o ticket de login Steam gerado pelo seu jogo é enviado ao `raceos.gg` para buscar seu perfil. Nenhuma senha da Steam é lida ou guardada.
* **Badges:** os 5 oficiais: Rookie, Good Driver, Trusted Driver, Warning e Probation (independentes do SR).
* **Sempre atualizado:** renovado a cada 5 minutos e reconferido depois de cada corrida (o jogo atualiza DR / SR / badge ao fim da corrida, então podem subir, cair ou mudar de badge).
* **Seguro em falhas:** se o serviço ficar fora do ar, o último valor válido é mantido (com nova tentativa automática). Uma consulta que falha nunca troca dados reais por um valor padrão.
* Ainda sem dados? O ícone e o tooltip simplesmente não aparecem.

```json
"racecontrol": {
  "enabled": true,
  "raceos": { "enabled": true },
  "local_refresh_seconds": 300,
  "post_race_schedule_seconds": [10, 20, 40, 60, 90, 120, 180, 300],
  "session_lookup": false
}
```
`session_lookup` (desligado por padrão) também consulta os outros pilotos da sessão, pelo nome.

## 🚀 Funcionalidades

*   **Detecção Automática:** Carro, Pista, Classe e Tipo de Sessão.
*   **Status Inteligente:** Menus, Treino, Qualificação, Warmup ou Corrida, Online ou offline.
*   **Dados em Tempo Real:** Tempo restante ou contagem de voltas, posição na classe e grid da sessão.
*   **Posição por classe:** `P5/12` é sua posição entre os carros da sua própria classe.
*   **Alternância Carro / Pista** na imagem, com tempos configuráveis.
*   **Driver Rating, Safety Rating e Badge** (opt-in, veja acima).
*   **Multi-Idioma:** Português, Inglês e Espanhol (detectado automaticamente).
*   **Início Automático:** opcional, junto com o Windows.
*   **Zero Configuração:** basta abrir e jogar. Sem configurar IP ou porta.

## ⚙️ Configurações (`config.json`)

| Chave | Padrão | Descrição |
| :--- | :---: | :--- |
| `show_party_size` | `true` | Mostra `(carros na sessão de vagas)` na linha 1 (só online) |
| `cycle_track_image` | `true` | Alterna as imagens de carro e pista |
| `cycle_car_seconds` | `10` | Segundos na imagem do carro |
| `cycle_track_seconds` | `5` | Segundos na imagem da pista |
| `autostart` | `false` | Iniciar com o Windows |
| `steamid` | `""` | Opcional. Só para consultas manuais |
| `racecontrol.raceos.enabled` | `false` | DR / SR / Badge automáticos (veja acima) |

Copie `config.example.json` para `config.json` para começar. Os logs ficam em `lmu_rpc.log`.

## 📥 Instalação

1.  Vá para a página de [**Releases**](https://github.com/uWaazy/LMU-RPC-Mod/releases).
2.  Baixe o arquivo `.zip` mais recente (ex: `LMU_RPC_vX.Y.zip`).
3.  Extraia em qualquer lugar do seu PC.
4.  Execute o `LMU_RPC.exe` e inicie o RPC pelo app.
5.  Abra o **Le Mans Ultimate** e divirta-se!

## 🧪 Rodando pelo código-fonte

```bash
pip install -r requirements.txt
python lmu_rpc.py
```

Python 3.10+ no Windows. Para gerar o `.exe` use Python 3.11 ou 3.12 (`python build.py`).

**Preview:** `pip install -r requirements-preview.txt` e depois `python lmu_preview.py` (ou `run_preview.bat`) abre uma versão editável do app: escolha carro, pista, sessão, tempo, posição e rating à mão e veja no Discord na hora, sem o jogo.

## 🛠️ Projetos Relacionados

Conheça o **LMU Tools**, uma aplicação desktop que ajuda pilotos a otimizar setups e estratégias de corrida de forma rápida e intuitiva.

[![LMU Tools](https://img.shields.io/badge/GitHub-LMU_Tools-blue?style=for-the-badge&logo=github)](https://github.com/uWaazy/LMU-Tools/tree/main)

## 🤝 Suporte e Feedback

Encontrou um bug? Tem uma sugestão? Junte-se ao nosso servidor no Discord!

[![Discord](https://img.shields.io/discord/1463577784394973392?style=for-the-badge&logo=discord&logoColor=white&label=Entrar%20no%20Discord)](https://discord.gg/cE6B2azY73)

---

**Desenvolvido por uWaazy**

<a href="https://ko-fi.com/uwaazy" target="_blank">
  <img src="https://img.shields.io/badge/Support%20my%20Work-FF5E5B?style=for-the-badge&logo=kofi&logoColor=white" alt="Ko-fi Donate">
</a>
