import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";

/*
    This is the entry point for the React application.

    React starts here and renders <App /> into the HTML
    element with the ID "root".
*/

createRoot(
    document.getElementById("root")
).render(
    <StrictMode>
        <App />
    </StrictMode>
);