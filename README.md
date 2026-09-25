# Atlas — assistente de voz com personagem, para Windows

Assistente de voz local, com um personagem animado na tela. Fica em segundo
plano na bandeja do sistema; ao ouvir **"Atlas"** (ou clicar em "Perguntar
agora" na bandeja), ele aparece, ouve a pergunta em português, consulta a IA
(Google Gemini) — pesquisando na web quando for preciso — e responde em voz
alta, com a boca do personagem sincronizada.

Inspirado no [Pynkaro](https://github.com/ralbuque/Pynkaro) (ralbuque), um
protótipo para macOS/Swift. O Atlas é uma reimplementação nativa para
Windows, em Python: veja [`MAPA_PYNKARO.md`](MAPA_PYNKARO.md) para a
correspondência entre os dois projetos.

## Privacidade

- Wake word e transcrição da pergunta: **modelo Vosk rodando localmente**
  (nenhum áudio do microfone sai do computador).
- Resposta falada: voz do Windows (SAPI, local) por padrão; ElevenLabs é
  opcional (só o **texto** da resposta viaja pela rede, nesse caso).
- Único tráfego de rede por padrão: o **texto** da pergunta para a API do
  Google Gemini (`generativelanguage.googleapis.com`).
- Chaves de API ficam no **Gerenciador de Credenciais do Windows**, nunca em
  arquivo de configuração, log ou neste repositório.

## Requisitos

- Windows 10/11, Python 3.11+ (testado com 3.13).
- Microfone e saída de áudio funcionando.
- Chave da API do **Gemini** (obrigatória): crie em
  https://aistudio.google.com/apikey — cobrança por uso, separada de
  qualquer assinatura do Gemini/Google One.
- Chave da **ElevenLabs** (opcional, para voz mais natural): crie em
  https://elevenlabs.io/app/settings/api-keys — também por uso.

## Instalação

```powershell
.\instalar.ps1
```

Instala as dependências Python (`requirements.txt`) e baixa o modelo de
reconhecimento de fala em português (Vosk, ~32MB, uma vez só).

## Como rodar (desenvolvimento)

```powershell
.\rodar.ps1
```

Na primeira execução, uma janela pede a chave da API do Gemini (obrigatória)
e da ElevenLabs (opcional). Depois disso o Atlas abre direto na bandeja.

## Gerar o executável

```powershell
.\build.ps1
```

Gera `dist\Atlas\Atlas.exe` com o PyInstaller (inclui o modelo de fala e os
sprites do avatar). Rode `instalar.ps1` antes, pelo menos uma vez, para
garantir que o modelo Vosk existe.

## Uso

1. O ícone na bandeja mostra o estado (aguardando, ouvindo, pensando,
   falando, pausado).
2. Diga **"Atlas, que horas são em Tóquio?"** — ou apenas "Atlas" e espere o
   avatar aparecer antes de perguntar. Também dá pra clicar em
   **"Perguntar agora"** no menu da bandeja, sem precisar falar o nome.
3. Fique em silêncio por ~1,8s depois de terminar a pergunta (ou ~6s se só
   disse "Atlas" e ainda não perguntou nada) para o Atlas processar.
4. Diga "esquece" ou "cancela" durante a pergunta para abortar sem consultar
   a IA.
5. Clique em "Configurações..." para trocar a palavra de ativação, o
   microfone/saída de áudio, a tela onde o avatar aparece, o tamanho dele,
   a voz do Windows e se o Atlas inicia com o Windows.

## O que foi testado de verdade nesta máquina

- Consulta real à API do Gemini (pergunta simples e pergunta com busca na
  web real, com fontes retornadas) — ✅ funcionando.
- Síntese de voz local (SAPI, voz `Microsoft Maria` pt-BR já instalada) com
  os eventos de sincronismo de boca — ✅ funcionando, sem erros.
- Abertura e fechamento do microfone real (Vosk) — ✅ sem erros; a detecção
  da palavra de ativação em fala real **ainda não foi validada com sua voz**
  (precisa de você falando "Atlas" perto do microfone).
- Janela do avatar (transparente, sempre no topo, sem roubar foco), ícone na
  bandeja e a máquina de estados completa (aguardando → ouvindo → pensando →
  falando) — ✅ testados de ponta a ponta neste computador, com avatar
  aparecendo/sumindo e trocando estado.
- ElevenLabs: implementado (visemas por timestamp + fallback para a voz
  local), mas **não testado de verdade** — não há chave configurada.

## O que falta você validar

Peço que você rode `.\rodar.ps1` e confira, com sua voz e seu microfone:

- Se "Atlas" é reconhecido de primeira (pode ajustar a palavra de ativação
  em Configurações se "Atlas" for confundido com outra palavra).
- Se o volume/posição do microfone está bom o bastante para o Vosk.
- Se o avatar aparece no monitor certo e no tamanho que você gosta.
- Perguntas seguidas, pausar/retomar, e o comportamento sem internet ou com
  chave inválida (deve avisar em vez de travar).

## Aparência do avatar (provisória)

O `atlas/assets/gen_avatar.py` gera um robozinho simples (traços limpos,
olhos grandes, fundo transparente) com os 5 sprites de boca necessários
(`avatar.png`, `avatar_mid.png`, `avatar_open.png`, `avatar_round.png`,
`avatar_fv.png`). É uma arte própria e provisória — troque os PNGs em
`atlas/assets/` (mesmo enquadramento/dimensões) por uma arte definitiva
quando quiser, sem mexer em código.

## Extensões futuras

- Conector de e-mail (Gmail API / Microsoft Graph), leitura primeiro, com
  confirmação explícita para qualquer envio — ver seção 7 do prompt
  original do projeto.
- Atalho de teclado global para "perguntar agora" (hoje só via bandeja).
- Avatar com rig 2D (Rive), como no Pynkaro original.

## Estrutura

```
run_atlas.py            entrada do executavel/dev
atlas/main.py            liga tudo (bandeja, avatar, assistente)
atlas/core/
  config.py               chaves (Credential Manager) + ajustes (JSON)
  speech_recognizer.py     Vosk + microfone, transcricao continua local
  voice_assistant.py       maquina de estados (wake word -> ... -> fala)
  gemini_client.py         API do Gemini, com busca no Google
  speaker.py               voz local (SAPI/pyttsx3)
  elevenlabs_speaker.py     voz ElevenLabs opcional, com lip sync por visemas
atlas/ui/
  avatar_window.py         janela transparente do personagem
  tray.py                  icone e menu na bandeja
  settings_window.py       configuracoes / onboarding
atlas/platform_/autostart.py  iniciar com o Windows (registro)
atlas/assets/              sprites do avatar + gerador
models/                    modelo Vosk pt-BR (baixado por instalar.ps1)
```
