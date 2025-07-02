# AI Agent Instructions for Agar.io Clone Project

## Purpose
This document provides guidance for AI agents working on the Agar.io Clone codebase.

## Project Structure
The project is organized into two main directories:
-   `server/`: Contains the Python FastAPI backend, including game logic and WebSocket handling.
-   `client/`: Contains the HTML, CSS, and JavaScript for the frontend client.

## Key Technologies
-   **Server:** Python 3.7+
    -   FastAPI: Web framework.
    -   Uvicorn: ASGI server.
    -   `websockets` library: For WebSocket communication.
-   **Client:**
    -   HTML5
    -   CSS3
    -   JavaScript (ES6+)
    -   HTML5 Canvas API: For rendering the game.

## Server-Side Notes
-   **Main Entry Point:** `server/main.py` initializes the FastAPI app and WebSocket endpoints.
-   **Game Logic:** Core game mechanics are implemented in `server/game.py`. This includes player movement, interactions, and game state updates.
-   **Configuration:** Game parameters (map size, speeds, masses, etc.) are defined in `server/config.py`.
-   **Running the Server:**
    ```bash
    cd server
    # Ensure requirements are installed: pip install -r requirements.txt
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
    ```
    The server will be accessible at `ws://localhost:8000/ws`.

## Client-Side Notes
-   **Main HTML File:** `client/index.html` is the entry point for the client.
-   **Main JavaScript File:** `client/js/main.js` handles client-side game logic, rendering, WebSocket communication, and user input.
-   **Styling:** `client/css/style.css` contains styles for the game page and UI elements like the leaderboard.
-   **Opening the Client:** After starting the server, open the `client/index.html` file directly in a modern web browser.

## Implemented Game Mechanics Overview
The game currently supports the following core features:
-   Player-controlled cells moving towards the mouse cursor.
-   Consumption of static pellets to gain mass.
-   Consumption of smaller player cells by larger ones.
-   Splitting of player cells (Spacebar).
-   Ejection of mass from player cells ('W' key).
-   Viruses that cause larger cells to burst into multiple smaller pieces upon collision.
-   Feeding viruses with ejected mass, potentially causing them to split and create a new virus.
-   A leaderboard displaying top players by mass.
-   Client-side interpolation for smoother visuals.

## Development & Debugging Tips
-   **Server Logs:** The FastAPI/Uvicorn server provides console logs. These are crucial for debugging server-side game state, player connections, and actions.
-   **Client Browser Console:** Use the browser's developer tools (Console, Network tabs) to inspect WebSocket messages, client-side errors, and rendering performance.
-   **Coordinate Systems:** Be mindful of the distinction between world coordinates (used by the server and for game logic) and screen coordinates (used for rendering on the client's canvas, relative to the viewport).
-   **Authoritative Server:** The server is the authority on game state. Client-side logic should primarily focus on sending input, receiving state updates, and rendering. Avoid implementing game logic independently on the client that could lead to desynchronization.
-   **Modularity:**
    -   When adding new game entities, consider creating new classes or structured objects in `server/game.py`.
    -   For new player actions, ensure:
        1.  Client sends the appropriate message (usually to `/ws` endpoint, handled in `server/main.py`).
        2.  `server/main.py` parses the message and calls the relevant function in `server/game.py` (e.g., `handle_player_input`).
        3.  `server/game.py` updates the game state.
        4.  The updated state is broadcast back to clients.
        5.  Client (`client/js/main.js`) handles the updated state for rendering.
-   **Configuration:** New game parameters should generally be added to `server/config.py` for easy tuning.

## Programmatic Checks
There are currently no automated programmatic checks (`AGENTS_CHECKS.md` or similar) defined for this project. Adherence to the instructions and careful testing of changes are expected.
