"""Interactive CLI for querying Hindu scriptures.

Usage:
    python scripts/rag/cli.py

Commands:
    /filter source Bhagavad Gita   - Filter by scripture
    /filter category shruti         - Filter by category
    /filter tradition vedanta       - Filter by tradition
    /filter clear                   - Clear all filters
    /top 10                         - Change number of results
    /agent                          - Toggle agentic mode
    /quit                           - Exit
"""

from api_security import UserInputError
from config import RAGConfig

from query import query_rag


def print_banner():
    print("\n" + "=" * 60)
    print("  Hindu Scriptures RAG — Ask questions about sacred texts")
    print("=" * 60)
    print("Commands: /filter, /top, /agent, /quit")
    print("Example: What does the Bhagavad Gita say about duty?")
    print()


def format_sources(sources: list[dict]) -> str:
    lines = []
    for i, s in enumerate(sources, 1):
        source = s.get("source_text", "Unknown")
        chapter = s.get("chapter_name", "")
        verse = s.get("verse_num", "")
        ref = source
        if chapter:
            ref += f" - {chapter}"
        if verse:
            ref += f", Verse {verse}"
        score = s.get("score", 0)
        chunk_type = s.get("chunk_type", "verse")

        if chunk_type == "commentary":
            author = s.get("author", "")
            ref += f" [Commentary by {author}]"

        lines.append(f"  [{i}] {ref}  (score: {score:.3f})")
    return "\n".join(lines)


def main():
    config = RAGConfig()
    filter_dict: dict = {}
    agent_mode = False

    print_banner()

    while True:
        try:
            mode_label = " [agent]" if agent_mode else ""
            user_input = input(f"\nYou{mode_label}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() == "/quit":
            print("Goodbye!")
            break

        if user_input.lower() == "/agent":
            agent_mode = not agent_mode
            print(f"Agent mode: {'ON' if agent_mode else 'OFF'}")
            continue

        if user_input.lower().startswith("/top "):
            try:
                n = int(user_input.split()[1])
                config.top_k = n
                print(f"Top-k set to {n}")
            except (ValueError, IndexError):
                print("Usage: /top <number>")
            continue

        if user_input.lower().startswith("/filter"):
            parts = user_input.split(maxsplit=2)
            if len(parts) >= 2 and parts[1].lower() == "clear":
                filter_dict.clear()
                print("Filters cleared.")
            elif len(parts) == 3:
                field = parts[1].lower()
                value = parts[2]
                valid_fields = {
                    "source": "source_text",
                    "category": "category",
                    "tradition": "tradition",
                }
                if field in valid_fields:
                    filter_dict[valid_fields[field]] = value
                    print(f"Filter set: {field} = {value}")
                else:
                    print(f"Unknown filter field '{field}'. Valid: source, category, tradition")
            else:
                print("Usage: /filter <source|category|tradition> <value>")
                print("       /filter clear")
            if filter_dict:
                print(f"Active filters: {filter_dict}")
            continue

        # Query
        if agent_mode:
            print("\nAgent is thinking...")
            try:
                from agent.react_loop import run_agent

                result = run_agent(user_input, config=config)
            except UserInputError as e:
                print(f"\nInvalid input: {e}")
                continue
            except Exception as e:
                print(f"\nError: {e}")
                continue

            print(f"\n{'—' * 50}")
            print(result["answer"])
            if result.get("tool_calls"):
                print(f"\n{'—' * 50}")
                print(f"Tools used: {len(result['tool_calls'])}")
                for tc in result["tool_calls"]:
                    print(f"  - {tc['name']}({tc.get('input_summary', '')})")
        else:
            print("\nSearching scriptures...")
            try:
                result = query_rag(user_input, config, filter_dict if filter_dict else None)
            except UserInputError as e:
                print(f"\nInvalid input: {e}")
                continue
            except Exception as e:
                print(f"\nError: {e}")
                continue

            print(f"\n{'—' * 50}")
            print(result["answer"])
            print(f"\n{'—' * 50}")
            print(f"Sources ({len(result['sources'])} passages):")
            print(format_sources(result["sources"]))


if __name__ == "__main__":
    main()
