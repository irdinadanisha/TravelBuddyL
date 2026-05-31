# TravelBuddy France Architecture

## Goal

Build a France-focused travel chatbot that:

- recommends places locals genuinely enjoy
- avoids common tourist traps when possible
- explains why each recommendation fits the traveler
- shows recommended places on a map inside chat
- exports the final itinerary as PDF

## Recommended Technical Shape

### Frontend

- React + Vite
- Chat layout with two synchronized panels:
  - conversation and itinerary cards
  - map with recommended places
- PDF export button after an itinerary is generated

### Backend

- FastAPI for API and orchestration
- Modular planning pipeline:
  - request parsing
  - intent and constraint extraction
  - retrieval
  - ranking
  - itinerary planning
  - response formatting
  - PDF export

## Mapping the Flowchart to Components

### 1. User Input

Frontend chat box sends a prompt such as:

`I'm in Paris for 3 days, I like food markets, bookstores, quiet neighborhoods, and I want to avoid overcrowded tourist spots.`

### 2. Web Frontend

The React app:

- stores the conversation
- sends the user message to the backend
- renders itinerary cards
- updates map markers based on response places

### 3. API Gateway

For the first version, this can just be the FastAPI router layer. If traffic grows later, it can sit behind a reverse proxy or API gateway service.

### 4. Backend Orchestrator

A single planner service coordinates the rest of the pipeline and decides whether to continue or return an error.

### 5. Prompting Module

In production this should:

- extract destination, dates, budget, travel style, pace, interests
- classify whether the request is itinerary-related
- generate natural language explanations

For now the scaffold uses deterministic extraction so the system can run before an LLM is wired in.

### 6. RAG Retrieval

The retrieval layer should eventually combine:

- curated France local recommendations
- neighborhood and venue metadata
- embeddings for semantic search
- business rules such as avoiding places tagged as tourist traps

### 7. Embedding Search and Candidate Ranking

Good ranking signals:

- match to interests
- fit to city or region
- local authenticity score
- crowding or tourist-trap penalty
- daypart suitability

### 8. Agent Planning Layer

This layer converts ranked places into an itinerary with:

- ordered stops
- short explanations
- map-ready coordinates
- a practical day structure

### 9. Save or Display Results

The backend returns JSON for on-screen rendering and a PDF export endpoint for saving.

## Suggested Data Model

### Travel Request

- raw query
- destination
- trip length
- interests
- dislikes
- budget
- pace

### Place

- name
- city
- category
- reason to recommend
- why locals like it
- tourist trap level
- latitude
- longitude

### Itinerary

- summary
- city
- themes
- recommended stops
- avoidance notes

## Recommended Next Steps

1. Build a France seed dataset for Paris, Lyon, Marseille, Nice, Bordeaux, Strasbourg, Lille, and small-town picks.
2. Add a real map provider.
3. Add an LLM extraction + explanation layer.
4. Replace in-memory data with a database plus vector store.
5. Add session persistence and user authentication if needed.
