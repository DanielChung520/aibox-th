"""Text chunking utilities."""

DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 100


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    if not text.strip():
        return []
    chars = list(text.strip())
    chunks: list[str] = []
    start = 0
    while start < len(chars):
        end = start + chunk_size
        chunk = "".join(chars[start:end])
        if chunk.strip():
            chunks.append(chunk.strip())
        start += chunk_size - chunk_overlap
        if start >= len(chars):
            break
    return chunks
