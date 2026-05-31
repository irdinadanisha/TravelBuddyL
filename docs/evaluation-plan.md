# TravelBuddy Evaluation Plan

This project follows the proposal's comparison between an LLM-only planner, a basic RAG planner, and the proposed personalized RAG travel buddy.

## Systems To Compare

1. LLM-only baseline: generate an itinerary without retrieved Reddit or Google Maps evidence.
2. Basic RAG baseline: retrieve candidate places, but use minimal personalization.
3. Proposed TravelBuddy agent: retrieve source-backed places, extract user constraints, split by trip duration, and show source evidence.

## Test Set

Create 20 to 50 France travel prompts that cover:

- City, date, and trip duration requests.
- Budget, mood, pace, and travel-style constraints.
- Interests such as cafes, museums, markets, bookstores, restaurants, and quiet walks.
- Avoidance constraints such as tourist traps, crowds, famous landmarks, and overpriced places.

## Metrics

- Precision@K: how many top recommended stops are relevant to the prompt.
- Recall@K: how many known good candidate stops the system includes.
- nDCG@K: whether the best local-feeling places appear near the top.
- Factual accuracy: whether opening hours, ratings, and place details match Google Maps data.
- Groundedness: whether each recommendation has Reddit or Google Maps evidence.
- Personalization score: whether budget, mood, pace, travel style, and interests are reflected.
- Authenticity score: whether the result avoids generic tourist-trap recommendations.
- Constraint satisfaction: whether the plan respects duration, city, avoidance, and open/closed status.
- Hallucination rate: whether any unsupported places, claims, or source references appear.

## Current Prototype Support

- `TravelIntent` extracts destination, duration, interests, avoid list, pace, visit day, budget, mood, and travel style.
- `/api/chat` returns evidence items from Reddit or Google Maps when available.
- `/api/sessions` stores chat turns and latest itineraries locally as a development replacement for the proposal's DynamoDB storage.
- Google Maps enrichment supplies rating, review count, opening hours, and open/closed labels.
- Reddit ingestion supplies community-source recommendations for more local-feeling suggestions.

## Next Research Step

Export chat responses for the same prompt set across the three systems, then score them manually or with a rubric-based evaluator. Keep the final report focused on whether source-backed personalized RAG improves trust, authenticity, and constraint satisfaction compared with an LLM-only response.
