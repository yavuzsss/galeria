import type { SearchResult } from "../api";
import { ResultCard } from "./ResultCard";

interface Props {
  results: SearchResult[];
  dimmed: boolean;
  onOpen: (index: number) => void;
}

export function ResultGrid({ results, dimmed, onOpen }: Props) {
  return (
    <ul className={`grid${dimmed ? " grid--dimmed" : ""}`} aria-busy={dimmed}>
      {results.map((result, i) => (
        <li key={`${result.kind}-${result.id}`}>
          <ResultCard result={result} rank={i} onOpen={() => onOpen(i)} />
        </li>
      ))}
    </ul>
  );
}
