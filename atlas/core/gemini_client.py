"""Cliente da API do Google Gemini para o Atlas.

Mesma responsabilidade que teria um cliente Claude: manda a pergunta (com
historico da conversa) para o modelo, com a ferramenta de busca na web
ligada (Google Search grounding) quando a pergunta precisar de dados
atuais, e devolve o texto para ser falado.
"""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from typing import Optional

from google import genai
from google.genai import types

from . import config

log = logging.getLogger("atlas.gemini")

MAX_HISTORY = 20  # numero de turnos (usuario+modelo juntos) mantidos


@dataclass
class AskResult:
    text: str
    used_web_search: bool
    sources: list[str]


class GeminiError(RuntimeError):
    pass


class GeminiClient:
    def __init__(self) -> None:
        settings = config.load_settings()
        self.model = settings.gemini_model
        self.web_search_enabled = settings.web_search_enabled
        self.history: list[types.Content] = []
        self._client: Optional[genai.Client] = None
        self._client_key: Optional[str] = None

    def _client_for_current_key(self) -> genai.Client:
        key = config.get_gemini_key()
        if not key:
            raise GeminiError(
                "Chave do Gemini nao configurada. Abra Configuracoes do Atlas."
            )
        if self._client is None or self._client_key != key:
            self._client = genai.Client(api_key=key)
            self._client_key = key
        return self._client

    def _system_prompt(self) -> str:
        now = datetime.datetime.now()
        dias = ["segunda-feira", "terca-feira", "quarta-feira", "quinta-feira",
                "sexta-feira", "sabado", "domingo"]
        meses = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho",
                 "agosto", "setembro", "outubro", "novembro", "dezembro"]
        data_str = f"{dias[now.weekday()]}, {now.day} de {meses[now.month - 1]} de {now.year}, {now.strftime('%H:%M')}"
        tz = str(datetime.datetime.now().astimezone().tzinfo)

        return f"""Voce e o Atlas, um assistente de voz local rodando no computador do usuario.
Responda sempre em portugues do Brasil, em um texto pensado para ser lido em voz alta.
Seja breve por padrao: normalmente de uma a tres frases curtas, sem enrolacao.
Se o usuario pedir mais detalhes explicitamente (ex.: "explica melhor", "com mais detalhes"),
pode responder de forma mais completa, mas ainda direta.
Nunca use markdown, listas, simbolos, asteriscos ou emojis: e texto que vira audio.
Tom informal e cordial, como alguem prestativo — sem forcar piadas ou humor.
Primeiro responda exatamente o que foi perguntado, com informacao correta.
Se nao tiver certeza de algo, ou se uma busca falhar ou nao trouxer dado confiavel,
diga isso claramente em vez de inventar uma resposta.
Data e hora atuais no computador do usuario: {data_str}, fuso horario {tz}.
Use essa informacao para perguntas sobre data e hora; para a hora em outros lugares,
calcule a diferenca de fuso a partir dela.
Voce tem acesso a busca no Google: use-a quando a pergunta envolver fatos atuais
(noticias, cotacoes, clima, esportes, eventos recentes). Nao cite URLs em voz alta —
as fontes sao mostradas separadamente na tela."""

    def ask(self, question: str) -> AskResult:
        client = self._client_for_current_key()

        self.history.append(types.Content(role="user", parts=[types.Part(text=question)]))
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]

        tools = [types.Tool(google_search=types.GoogleSearch())] if self.web_search_enabled else None
        config_obj = types.GenerateContentConfig(
            system_instruction=self._system_prompt(),
            max_output_tokens=1000,
            tools=tools,
        )

        try:
            response = client.models.generate_content(
                model=self.model,
                contents=self.history,
                config=config_obj,
            )
        except Exception as exc:  # google.genai levanta varios tipos de erro de API
            raise GeminiError(str(exc)) from exc

        text = (response.text or "").strip()
        if not text:
            raise GeminiError("A API nao retornou texto.")

        used_web_search = False
        sources: list[str] = []
        candidates = getattr(response, "candidates", None) or []
        for cand in candidates:
            grounding = getattr(cand, "grounding_metadata", None)
            if grounding is None:
                continue
            chunks = getattr(grounding, "grounding_chunks", None) or []
            if chunks:
                used_web_search = True
            for chunk in chunks:
                web = getattr(chunk, "web", None)
                if web is not None and getattr(web, "uri", None):
                    sources.append(web.uri)

        self.history.append(types.Content(role="model", parts=[types.Part(text=text)]))
        return AskResult(text=text, used_web_search=used_web_search, sources=sources)

    def reset_history(self) -> None:
        self.history = []
