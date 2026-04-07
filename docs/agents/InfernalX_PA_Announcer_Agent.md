# InfernalX PA Announcer Agent

## Overview
The **PA Announcer Agent** is the human-translation layer of the InfernalX Multi-Agent architecture. It acts directly upon the raw JSON and coordinate logistics outputted by the Evacuation Officer, summarizing those deep-thought survival plans into crisp, localized public address (PA) notifications embedded immediately onto the graphical interface.

## LangChain Output Parsing
Instead of writing complex regex parsers to strip agent logs, the `PA_Announcer_Agent` operates exclusively at the tail end of the LangGraph chain. Receiving the state dictionary compiled by the Evacuation Officer and Fire Chief, the PA Announcer applies a restrictive system prompt preventing hallucination and enforces a strictly professional tone.

## Future Human Interface & Latency Zero
As inference speeds increase and TTS (Text-to-Speech) APIs optimize, this agent is the foundation for absolute autonomous communication. The raw text it outputs will be injected directly into synthetic voice architectures, shouting localized warnings unique to different sides of a fiery warehouse dynamically based purely on the physical LLM interpretation.
