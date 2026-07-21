# Architecture

AI Enterprise OS uses a domain-oriented monorepo with clear separation between product applications, platform services, AI runtime, and infrastructure.

```mermaid
flowchart TD
  A[Apps: Web Admin / Web Portal / Mobile] --> G[API Gateway]
  G --> S1[Identity Service]
  G --> S2[Organization Service]
  G --> S3[Workflow Service]
  G --> S4[Rules Service]
  G --> S5[Audit Service]
  G --> S6[Notification Service]
  G --> S7[Knowledge Service]
  G --> S8[Search Service]
  G --> S9[AI Gateway]
  S1 --> P[(PostgreSQL)]
  S2 --> P
  S3 --> P
  S4 --> P
  S5 --> P
  S6 --> R[(Redis)]
  S7 --> Q[(Qdrant)]
  S8 --> Q
  S9 --> O[Ollama]
  S1 --> N[(NATS JetStream)]
  S2 --> N
  S3 --> N
  S4 --> N
  S5 --> N
  S6 --> N
  S7 --> N
  S8 --> N
  S9 --> N
  M[MinIO]:::infra
  K[Keycloak]:::infra
  OBS[Prometheus + Loki + Tempo + Grafana]:::infra
  classDef infra fill:#f8f8f8,stroke:#888;
```

## Design decisions

- Service-per-domain boundaries to support independent scale and ownership.
- Shared package layers for cross-service consistency (logging, config, security, telemetry, event contracts).
- Docker Compose as local orchestration baseline for fast onboarding.
- Build and lint automation centralized via `Makefile`, pre-commit, and GitHub Actions.
