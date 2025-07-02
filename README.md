# Agar.io Clone

A multiplayer browser game inspired by Agar.io, built with Python (FastAPI) for the backend and JavaScript (HTML5 Canvas) for the frontend. Players control cells, consume pellets and other smaller player cells to grow, and can utilize mechanics like splitting, ejecting mass, and interacting with viruses.

## Features
-   **Real-time Multiplayer:** Connect and play with others in the same game world.
-   **Cell Growth:** Consume pellets and smaller player cells to increase your mass.
-   **Splitting:** Press `Spacebar` to split your cell(s) into smaller pieces, often used for attacking or escaping.
-   **Ejecting Mass:** Press `W` to eject small pieces of mass. This can be used to feed other players, feed viruses, or slightly reduce your size.
-   **Viruses:** Green, spiky stationary objects.
    -   Larger cells colliding with a virus will burst into many smaller pieces.
    -   Feeding a virus with ejected mass will cause it to grow. If it grows large enough, it will shoot out a new virus in the direction the mass came from.
-   **Leaderboard:** Displays the top players ranked by their total mass.
-   **Smooth Gameplay:** Client-side interpolation for smoother visual movement of cells.
-   **Optimized Network Updates:** Utilizes Area of Interest (AoI) filtering, where the server sends clients only data relevant to their immediate vicinity, significantly reducing bandwidth and improving scalability.

## Tech Stack
-   **Backend:**
    -   Python 3.7+
    -   FastAPI (for WebSocket handling and API structure)
    -   Uvicorn (as the ASGI server)
    -   `websockets` (implicitly used by FastAPI for WebSocket connections)
-   **Frontend:**
    -   HTML5
    -   CSS3
    -   JavaScript (ES6+)
    -   HTML5 Canvas API (for all game rendering)

## Setup and Running

### Prerequisites
-   Python 3.7 or newer.
-   `pip` (Python package installer).

### Backend Setup
1.  **Navigate to the server directory:**
    ```bash
    cd server
    ```
2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Run the server:**
    ```bash
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
    ```
    The server will start, typically listening on `http://0.0.0.0:8000`. The WebSocket endpoint will be `ws://localhost:8000/ws`.

### Frontend Setup
1.  **Ensure the backend server is running.**
2.  **Open the client file:**
    Navigate to the `client/` directory and open `index.html` in a modern web browser (e.g., Chrome, Firefox, Edge, Safari).

## Gameplay Instructions
-   **Movement:** Your cell(s) will follow your mouse cursor.
-   **Growth:**
    -   Move over small, colored, static **pellets** to consume them and gain mass.
    -   Move over other player cells that are smaller than your cell to consume them.
-   **Survival:** Avoid larger player cells, as they can consume you!
-   **Actions:**
    -   **Split (`Spacebar`):** Divides your current cell(s) into smaller ones. This can be used to cover more area, shoot a cell forward to consume a smaller target, or as a defensive maneuver. Split cells have a temporary cooldown before they can merge back together.
    -   **Eject Mass (`W` key):** Shoots a small piece of mass in the direction of your mouse cursor. This costs a small amount of your cell's mass. Ejected mass can be eaten by other cells (including your own) or fed to viruses.
-   **Viruses (Green Spiky Cells):**
    -   If one of your cells is significantly larger than a virus and consumes it, your cell will burst into many smaller pieces.
    -   You can "feed" a virus by ejecting mass into it. If a virus consumes enough ejected mass, it will split, shooting out a new virus in the direction the mass came from.

## Development Notes
-   The server is authoritative for all game logic and state.
-   The client primarily handles rendering and sending user inputs.
-   Game configuration (speeds, masses, limits) can be found in `server/config.py`.
-   The server employs Area of Interest (AoI) filtering (`PLAYER_AREA_OF_INTEREST_RADIUS` in `server/config.py`) to send tailored game state updates to each client, reducing the data load for entities outside a player's vicinity.

## Future Enhancements (Potential)
-   More advanced server-side optimizations (e.g., quadtrees for collision detection for entity filtering).
-   Client-side prediction for even smoother local player movement.
-   Persistent user accounts and scoring.
-   Different game modes (e.g., Teams, Experimental).
-   Mobile-friendly controls and UI.
-   Improved visual aesthetics and animations.
