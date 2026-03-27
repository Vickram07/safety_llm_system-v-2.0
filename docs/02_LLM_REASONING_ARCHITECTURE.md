# LLM Reasoning Architecture

## The "Safety-Locked" Approach
Standard LLMs are creative and unpredictable. To make one "God-Level" for safety, we lobotomize its creativity and amplify its reasoning.

## Mechanism
1.  **System Prompt Locking**:
    -   We explicitly forbid "assuming" data.
    -   We force a specific output structure (Situation -> Threat -> Recommendation).
2.  **Modelfile Parameters**:
    -   `temperature 0.0`: Ensures the same input always yields the same output.
    -   `top_p 0.5`: Limits vocabulary to the most likely tokens, reducing hallucinations.

## Cognitive Pipeline
1.  **Ingest**: Read JSON state.
2.  **Validate**: Check for contradicting sensors (e.g., Fire Alarm = ON, but Temp = 20°C).
3.  **Declare Uncertainty**: If contradiction exists, output "UNCERTAINTY DETECTED".
4.  **Triangulate**: If multiple sources agree (Smoke + High Temp), escalate to "CONFIRMED THREAT".
5.  **Advise**: Generate specific instruction.

## Future: Moral Pause
Later, a "Moral Pause" module will intercept the pipeline between Step 4 and 5 to evaluate ethical implications of the recommendation (e.g., locking a door to contain fire vs. trapping a person).
