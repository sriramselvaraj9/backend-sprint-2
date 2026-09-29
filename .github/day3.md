Create Day 3 of my FastAPI learning project.

IMPORTANT:
- I am a beginner.
- Keep the implementation simple and easy to understand.
- Use ONLY concepts I have learned so far and the concepts required by today's exercise.
- Do NOT add extra features, advanced patterns, unnecessary abstractions, or unrelated libraries.
- Do NOT change the existing Day 1 or Day 2 folders.
- Day 3 must be based on Day 2.

CURRENT PROJECT:
The project is a Film Review Platform built with FastAPI.

CURRENT FOLDER STRUCTURE:
sprint2/
├── day1/
├── day2/
├── .gitignore
├── .python-version
└── pyproject.toml

CREATE:
sprint2/day3/

STEP 1 — INHERIT DAY 2
- Copy the complete Day 2 project into the new day3 folder.
- Preserve the existing Day 2 functionality.
- Day 3 should start as a working copy of Day 2.
- Do not modify day1 or day2.

STEP 2 — TODAY'S TOPICS

Today's topic is:

FastAPI Dependency Injection & Configuration

Exercise:
Film Review Platform — Configuration & Shared Dependencies

The API needs:
1. Centralized configuration
2. Dependency injection
3. Shared database session dependency
4. Request trace identifier dependency

IMPLEMENT ONLY THE FOLLOWING:

1. CENTRALIZED CONFIGURATION

Create a dedicated configuration module.

The configuration must load these values from a .env file:

- DATABASE_URL
- TOKEN_SECRET_KEY
- ACCESS_TOKEN_EXPIRE_MINUTES
- REFRESH_TOKEN_EXPIRE_DAYS
- ALLOWED_CORS_ORIGINS
- API_VERSION

Use a typed settings/config class.

Create ONE config object from that class.

The config object must be created once when the config module is imported.

Other modules must use this single config object.

IMPORTANT:
- Environment variable reads must exist ONLY inside the config module.
- Do NOT use os.getenv() anywhere outside the config module.
- Do NOT create separate Settings/config objects in other files.
- Do NOT directly read environment variables from routes, services, DAOs, or other modules.
- Missing required environment variables should cause the application to fail during startup with a clear validation error.

Create a .env file with simple development/example values.

Do not put real secrets in the file.

2. CONFIG DEPENDENCY

Create a dependency function that provides the config object.

Example idea:

get_config()

Routes that need configuration must receive it through:

Depends(get_config)

Do NOT directly import the config object inside route handler functions.

Keep the dependency simple.

3. PLACEHOLDER DATABASE DEPENDENCY

Create a reusable database dependency:

get_db()

For now, it does NOT need a real database.

It should yield a simple placeholder value such as:

"placeholder-db-session"

Structure it so that a real async database session can replace it later without changing route function signatures.

Use yield and proper cleanup structure, but do not implement a real database.

Example expected idea:

def get_db():
    db = "placeholder-db-session"
    try:
        yield db
    finally:
        pass

Keep it simple.

4. REQUEST TRACE ID DEPENDENCY

Create a dependency that provides a request trace identifier.

The dependency should:

- Read the trace ID from an incoming request header.
- Use a header such as:
  X-Request-ID
- If the header exists, return its value.
- If the header is missing, generate a new unique identifier.
- Make the trace ID injectable into routes using Depends().

Use FastAPI Header for reading the header.

Use Python's standard uuid module to generate a new identifier when the header is missing.

Keep this implementation simple.

5. APPLY DEPENDENCIES TO ROUTES

Apply ALL THREE dependencies:

- config dependency
- database dependency
- trace ID dependency

to at least TWO existing route handlers.

Use existing routes from the Day 2 Film Review Platform.

For example, two existing routes can receive:

config = Depends(get_config)
db = Depends(get_db)
trace_id = Depends(get_trace_id)

Do not create unnecessary new routes just to demonstrate dependencies.

Use the existing routes.

The route should be able to access these values and return/use them in a simple way where appropriate.

Do not add business logic that is not required.

6. DEPENDENCY CHAIN

Where appropriate, demonstrate the dependency concept simply.

Do not create unnecessary complex dependency chains.

Keep the dependency structure easy for a beginner to understand.

7. OPENAPI / DOCS VERIFICATION

Make sure the dependency declarations work correctly with FastAPI.

Run the application and verify:

/docs

Check that the routes using the request trace ID show the X-Request-ID header in the OpenAPI documentation.

Also verify that the API still starts successfully when all required .env values exist.

8. PROJECT STRUCTURE

Keep the structure consistent with the existing Day 2 project.

Add only the files needed for today's work.

For example, if appropriate:

day3/
├── app/
│   ├── ...
│   ├── config.py
│   └── dependencies.py
├── .env
└── ...

Do not blindly use this exact structure if Day 2 already has a different structure. Follow the existing Day 2 structure.

9. IMPORTANT LEARNING RESTRICTIONS

I am learning these concepts as a beginner.

Use only:
- FastAPI
- Depends
- dependency functions
- dependency chains
- yield for the placeholder resource
- Header
- Pydantic/Pydantic Settings for typed configuration
- .env configuration
- Python standard library uuid where required

Do NOT introduce:
- real database implementation
- SQLAlchemy
- async database drivers
- JWT implementation
- authentication implementation
- middleware
- Redis
- external configuration services
- advanced dependency classes
- unnecessary design patterns
- unnecessary abstractions
- extra features

The goal is to learn today's Dependency Injection and Configuration concepts, not to build production authentication or database functionality.

10. FINAL VERIFICATION

After implementation:

- Run the application.
- Verify it starts successfully.
- Open /docs.
- Verify at least two routes have the dependency declarations working.
- Verify X-Request-ID appears as a request header for routes using the trace dependency.
- Test one request with X-Request-ID.
- Test one request without X-Request-ID and confirm a new trace ID is generated.
- Confirm there are no os.getenv() calls outside the config module.
- Confirm Day 2 remains unchanged.

Finally, briefly explain:
1. What files were added/changed.
2. What each dependency does.
3. How the config object is created once and reused.
4. How the trace ID works.
5. How the placeholder database dependency can later be replaced without changing route signatures.

Do not add anything beyond today's requirements.