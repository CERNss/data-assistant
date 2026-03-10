## ADDED Requirements

### Requirement: Service-scoped Dockerfile locations
The logger and processor image definitions MUST be located in their corresponding service folders.

#### Scenario: Logger Dockerfile under logger service folder
- **WHEN** service files are inspected
- **THEN** logger image build definition MUST exist at `services/data_logger/Dockerfile`

#### Scenario: Processor Dockerfile under processor service folder
- **WHEN** service files are inspected
- **THEN** processor image build definition MUST exist at `services/data_processor/Dockerfile`

### Requirement: Compose uses service-scoped Dockerfiles
Docker Compose MUST reference service-scoped Dockerfile paths while preserving valid build configuration.

#### Scenario: Compose logger dockerfile path
- **WHEN** `docker-compose.yml` is loaded
- **THEN** logger build config MUST use `dockerfile: services/data_logger/Dockerfile`

#### Scenario: Compose processor dockerfile path
- **WHEN** `docker-compose.yml` is loaded
- **THEN** processor build config MUST use `dockerfile: services/data_processor/Dockerfile`
