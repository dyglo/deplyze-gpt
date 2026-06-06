function compactText(value) {
  return String(value || "").replace(/<\/c>/g, ", ").replace(/\s+/g, " ").trim();
}

export function locateSubjectFromPrompt(value) {
  let subject = compactText(value);
  subject = subject.replace(/^(point\s+to|locate|find|detect|show|ground)\s+/i, "").trim();

  const prefixPattern =
    /^(?:all\s+(?:the\s+)?instances\s+(?:of|that\s+match(?:es)?\s+the\s+following\s+description:)|a\s+single\s+instance\s+that\s+match(?:es)?\s+the\s+following\s+description:|the\s+region\s+that\s+matches\s+the\s+following\s+description:|the\s+text\s+referred\s+as)\s*/i;

  let previous = "";
  while (subject && subject !== previous) {
    previous = subject;
    subject = subject.replace(prefixPattern, "").trim();
  }

  return subject.replace(/[ .:]+$/g, "") || "target";
}

export function normalizeSuggestionText(value) {
  const text = compactText(value);
  if (/^locate\s+all\s+(?:the\s+)?instances\s+of\s+/i.test(text)) {
    return `Locate all instances of ${locateSubjectFromPrompt(text)}`;
  }
  if (/^point\s+to\s+/i.test(text)) {
    return `Point to ${locateSubjectFromPrompt(text)}`;
  }
  return text;
}
