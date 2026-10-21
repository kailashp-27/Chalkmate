# API contracts

`phase-one.md` defines the intended behavior and access boundaries.
`openapi.json` is exported from FastAPI; the browser's `api-schema.d.ts` is generated
from it with the pinned openapi-typescript command in the root README. CI checks
for drift. Domain business rules remain in Python.
