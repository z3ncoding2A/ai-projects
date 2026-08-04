#!/usr/bin/bash


npx add-mcp "https://gemini-api-docs-mcp.dev" && \
npx skills add google-gemini/gemini-skills --skill gemini-api-dev && \
npx skills add google-gemini/gemini-skills --skill gemini-live-api-dev && \
npx skills add google-gemini/gemini-skills --skill gemini-interactions-api 
