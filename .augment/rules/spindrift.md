---
type: "always_apply"
description: "Rules"
---

- Don't write tests until specifically requested. Its more important to get things working than to test. We can always add tests later when we have full context.
- Focus on getting the basic communication working first. We can always add features later.
- Do not write documentation until specifically requested. We can always add docs later when we have full context.
- Avoiding writing new code for parsing GCODE, managing state or other common tasks where possible. Use existing libraries where possible, including those from npmjs.org. Before writing extensive code for common tasks, prompt the user for other libraries to review.
- When using external libraries, priortize ones that have typescript definitions and types, as well as ones that are actively maintained and have a large user base.
- Records your progress and completions in a markdown file in artifacts/progress.md. Do not write README files at this time.
