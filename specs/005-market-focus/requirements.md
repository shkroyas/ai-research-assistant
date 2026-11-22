# 005 Market focus and evidence hygiene: requirements

**Status:** In progress.

## Problem

Live runs of *"Analyze the food delivery market in Nepal"* (22 Nov 2026) showed three defects:

1. **Drift to global data.** Search returned global market reports, so briefs named DoorDash, Uber Eats or Swiggy as Nepal's competitors and built the summary on worldwide figures.
2. **Redacted figures.** Paywalled pages (for example Statista) show masked values such as `US$ ****** million in ****`. These were cited as if they were facts.
3. **Noisy evidence.** Snippets kept markdown table fragments (`| --- |`) and symbols, which wasted the Analyst's context.

## Acceptance criteria

### R1 Focus

- **R1.1** The Researcher identifies the query's focus (the country, region or company the user asked about) together with the search plan. When planning fails, it falls back to the capitalised names in the query.
- **R1.2** Every search query contains at least one focus term. Code appends one if the model left it out.
- **R1.3** A finding is *on focus* when its title, URL or text mentions a focus term. On-focus findings are ranked first. At most 3 *background* findings are kept, as context.
- **R1.4** Findings sent to the Analyst are labelled `BACKGROUND` when they do not mention the focus.

### R2 Evidence hygiene

- **R2.1** Sentences with masked figures (`***`) are removed from snippets and scraped passages, and a result left with no usable text is dropped.
- **R2.2** Markdown table fragments, heading marks and stray symbols are removed from evidence text.
- **R2.3** Page passages prefer paragraphs that mention the focus.

### R3 Brief rules

- **R3.1** The Analyst names only competitors that operate in the focus market, or that compete directly with the focus company.
- **R3.2** Background findings may support at most one observation, which must be worded as global or general context.
- **R3.3** Code flags masked figures in the brief, and competitors supported only by background findings. These block approval in the same way as invalid citations.

### R4 Visibility

- **R4.1** The quality report and the Evidence tab show how many findings are on focus, and what the focus was.

### R5 Tests

- **R5.1** Offline tests cover focus detection, query completion, ranking with the background cap, text cleaning, the new grounding rules and the quality count.
