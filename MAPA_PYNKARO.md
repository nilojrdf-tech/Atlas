# Mapa: Pynkaro (referência) -> Atlas (Windows)

Referência examinada: https://github.com/ralbuque/Pynkaro, branch `main`,
commit `d699494c82a97ab9d013a27aeff3ad8cec96eb8f` (clonado em
`referencias/Pynkaro`, não versionado neste repositório — pasta local de
consulta).

| Pynkaro (Swift/macOS) | Atlas (Python/Windows) | Observação |
|---|---|---|
| `SpeechRecognizer.swift` (SFSpeechRecognizer on-device) | `atlas/core/speech_recognizer.py` (Vosk pt-BR local, via `sounddevice`) | 100% local; sem o limite de sessão de ~1 min do reconhecedor da Apple, então sem o watchdog de 45s do original |
| `VoiceAssistant.swift` (máquina de estados) | `atlas/core/voice_assistant.py` | Mesma máquina de estados e timers de silêncio (1,8s com pergunta / 6s sem), mesmas frases de cancelamento |
| `ClaudeClient.swift` (Anthropic) | `atlas/core/gemini_client.py` (Google Gemini) | Trocado por pedido explícito do usuário. Mesma ideia (histórico + busca na web server-side), agora com Google Search grounding no lugar do `web_search` da Anthropic |
| `Speaker.swift` (AVSpeechSynthesizer) | `atlas/core/speaker.py` (SAPI5 via `pyttsx3`, evento `started-word`) | Usa a voz `Microsoft Maria` pt-BR já instalada no Windows testado |
| `ElevenLabsSpeaker.swift` | `atlas/core/elevenlabs_speaker.py` | Mesmo endpoint `with-timestamps` e mapa de visemas; pede PCM em vez de mp3 para tocar direto com `sounddevice`, sem decoder externo |
| `AvatarWindow.swift` (NSWindow, modo sprites) | `atlas/ui/avatar_window.py` (PySide6) | Mesmo comportamento: canto inferior direito, sempre no topo, clique atravessa a janela, entrada/saída animada, legenda |
| `avatar.png` + variações | `atlas/assets/*.png` (gerado por `gen_avatar.py`) | Arte própria (robô), provisória |
| `Config.swift` (Keychain do macOS) | `atlas/core/config.py` (`keyring`, Gerenciador de Credenciais do Windows) | Mesma separação: segredos no cofre do SO, ajustes em JSON |
| `PynkaroApp.swift` / `AssistantController.swift` (menu bar) | `atlas/ui/tray.py` + `atlas/main.py` (`QSystemTrayIcon`) | Ícone por estado, pausar/retomar, configurações, "Perguntar agora" |
| — (não existia no Pynkaro) | `atlas/platform_/autostart.py` | Chave de registro `Run` do usuário atual, opcional |
| Rig Rive (`avatar.riv`, opcional) | Não implementado | Ficou como extensão futura — ver README |
| "Sugestores de notícias" / "modo opinião" (persona do Pynkaro) | Removido | Específico daquele projeto; o prompt do Atlas não usa opiniões cômicas aleatórias |

## Por que Python em vez de outra linguagem nativa

Decisão tomada olhando as dependências reais do original: `Speech`/`AVFoundation`
(Apple) não existem no Windows, e o app depende de STT contínuo, TTS com
callbacks de timing, uma janela overlay transparente e um ícone de bandeja —
tudo isso tem bibliotecas maduras em Python no Windows (`vosk`, `pyttsx3`
sobre SAPI5, `PySide6`, `sounddevice`), com instalação simples (`pip`) e sem
exigir toolchain nativo (C++/CMake) para o primeiro build. A troca custa
alguma performance de inicialização (~1-2s) frente a um binário nativo, mas
mantém o código legível e fácil de estender (ex.: conectores de e-mail
futuros).
