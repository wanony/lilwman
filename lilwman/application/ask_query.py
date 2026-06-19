from lilwman.domain.ports import EntryRepository, LLMPort


class AskQueryUseCase:
    def __init__(self, repo: EntryRepository, llm: LLMPort) -> None:
        self._repo = repo
        self._llm = llm

    async def execute(self, question: str) -> str:
        entries = await self._repo.search(question, limit=5)
        if not entries:
            return "Nothing in the wiki about that."

        snippets = "\n\n".join(
            f"[{i+1}] (tags: {', '.join(e.tags) or 'none'})\n{e.content}"
            for i, e in enumerate(entries)
        )
        prompt = (
            "You are a helpful assistant. Answer the question using only the "
            "provided wiki entries. Be concise.\n\n"
            f"Wiki entries:\n{snippets}\n\n"
            f"Question: {question}\n"
            "Answer:"
        )
        return await self._llm.generate(prompt)
