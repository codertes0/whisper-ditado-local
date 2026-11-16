# Ditado por voz local (Whisper)

Ditado por voz para Windows que roda **100% no seu computador**: segure uma tecla, fale e solte. O texto transcrito é colado no campo que estiver em foco, seja no navegador, no editor de código, no chat ou em qualquer outro app.

Fiz para escrever prompts longos no Claude Code falando em vez de digitar. É uma alternativa local e gratuita a ferramentas pagas de ditado: nenhum áudio sai da máquina.

## Como funciona

```
segura a tecla ──► grava o microfone (16 kHz, mono)
solta a tecla  ──► faster-whisper (large-v3) transcreve em português
               ──► texto vai para a área de transferência ──► Ctrl+V no campo em foco
```

- **GPU quando dá, CPU quando não dá:** tenta CUDA em `float16`; se a placa não estiver disponível, cai sozinho para CPU em `int8`.
- **DLLs CUDA via pip:** no Windows, o script encontra e pré-carrega as DLLs do cuBLAS/cuDNN instaladas pelos pacotes `nvidia-*`, então não é preciso instalar o CUDA Toolkit.
- **Filtro de silêncio (VAD)** e descarte de gravações muito curtas (toque acidental na tecla).
- **Push-to-talk global:** a tecla funciona em qualquer janela e é "engolida" enquanto você grava.
- **Modo chat opcional:** uma segunda tecla cola e já aperta Enter.
- Beeps curtos avisam o início e o fim.

## Instalação

Requisitos: Windows, Python 3.10+ e microfone. Uma GPU NVIDIA é opcional, mas deixa tudo bem mais rápido.

```bat
setup.bat      :: cria o .venv e instala as dependências (o modelo tem ~1,5 GB e é baixado na 1ª execução)
run.bat        :: inicia com terminal visível
```

Para rodar escondido em segundo plano, use `start-voice-claude.vbs`. Ele pode ir na pasta *Inicializar* do Windows para abrir junto com o sistema. Nesse modo, o log fica em `last-run.log`.

## Configuração

Tudo fica no topo de [`voice_claude.py`](voice_claude.py):

| Variável | Padrão | O que faz |
|---|---|---|
| `HOTKEY` | `"["` | Tecla de segurar para falar (ex.: `"f8"`, `"right ctrl"`) |
| `ENTER_HOTKEY` | `None` | Segunda tecla que cola **e** aperta Enter |
| `AUTO_ENTER` | `False` | Aperta Enter depois de colar sempre |
| `MODEL_SIZE` | `"large-v3"` | `tiny` · `base` · `small` · `medium` · `large-v3` |
| `BEAM_SIZE` | `5` | Mais alto = mais preciso, mais baixo = mais rápido |
| `LANGUAGE` | `"pt"` | Idioma da transcrição |

## Stack

Python · [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CTranslate2) · sounddevice · keyboard · pyperclip · CUDA (opcional)
