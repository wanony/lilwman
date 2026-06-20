from lilwman.domain.ports import EntryRepository, LLMPort

_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "have", "has", "had", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "what", "which", "who", "whom", "whose", "when", "where", "why", "how",
    "i", "me", "my", "we", "our", "you", "your", "it", "its",
    "this", "that", "these", "those", "there", "here",
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "about",
    "and", "or", "but", "not", "so", "if", "then", "than", "as",
    "tell", "give", "explain", "describe", "show", "find", "get",
    "please", "me", "some", "any", "no",
})


def _keywords(question: str) -> str:
    tokens = [t for t in question.split() if t.lower() not in _STOPWORDS and len(t) > 1]
    return " ".join(tokens)


class AskQueryUseCase:
    def __init__(self, repo: EntryRepository, llm: LLMPort) -> None:
        self._repo = repo
        self._llm = llm

    async def execute(self, question: str) -> str:
        entries = await self._repo.search(_keywords(question) or question, limit=5)
        if not entries:
            return "Nothing in the wiki about that."

        snippets = "\n\n".join(
            f"[{i+1}] (tags: {', '.join(e.tags) or 'none'})\n{e.content}"
            for i, e in enumerate(entries)
        )
        safe_question = question.replace('\n', ' ').replace('\r', ' ')
        prompt = (
            "You are a helpful assistant. Answer the question using only the "
            "provided wiki entries. Be concise.\n\n"
            f"Wiki entries:\n{snippets}\n\n"
            f"Question: {safe_question}\n"
            "Answer:"
        )
        return await self._llm.generate(prompt)
