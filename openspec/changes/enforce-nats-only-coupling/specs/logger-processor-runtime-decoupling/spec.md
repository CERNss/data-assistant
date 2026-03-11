## ADDED Requirements

### Requirement: Canonical runtime layout uses dual top-level service directories
The repository MUST expose canonical runtime entrypoints under top-level `data-logger/` and `data-processor/` service directories.

#### Scenario: Logger canonical entrypoint
- **WHEN** service files are inspected
- **THEN** logger entrypoint MUST exist at `data-logger/service/main.py`

#### Scenario: Processor canonical entrypoint
- **WHEN** service files are inspected
- **THEN** processor entrypoint MUST exist at `data-processor/service/main.py`

### Requirement: Logger and processor are decoupled at runtime boundary
Logger and processor MUST communicate through NATS protocol boundaries only, not through cross-imported local queue APIs.

#### Scenario: Logger does not call processor queue helpers
- **WHEN** logger code handles NATS publish failure
- **THEN** it MUST persist publish failure status and MUST NOT call processor-local queue enqueue functions

#### Scenario: Processor ingest boundary is NATS payloads
- **WHEN** processor receives a task
- **THEN** task ingest path MUST start from NATS payload decode and enqueue into processor-local queue

### Requirement: Service ownership boundaries are explicit
Each service runtime package MUST own its service-specific modules and avoid cross-service imports.

#### Scenario: Logger import isolation
- **WHEN** logger service modules are scanned
- **THEN** they MUST NOT import processor runtime modules

#### Scenario: Processor import isolation
- **WHEN** processor service modules are scanned
- **THEN** they MUST NOT import logger runtime modules

### Requirement: Compose references service-scoped Dockerfiles in top-level service folders
Docker Compose MUST build each service from its corresponding top-level Dockerfile path.

#### Scenario: Compose logger dockerfile path
- **WHEN** `docker-compose.yml` is loaded
- **THEN** logger build config MUST reference `dockerfile: data-logger/Dockerfile`

#### Scenario: Compose processor dockerfile path
- **WHEN** `docker-compose.yml` is loaded
- **THEN** processor build config MUST reference `dockerfile: data-processor/Dockerfile`
