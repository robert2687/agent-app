import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';

const container = document.getElementById('root');

if (container) {
  const root = createRoot(container);
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
} else {
    console.error("Fatal Error: The root container was not found in the DOM. The application cannot be mounted.");
    document.body.innerHTML = '<div style="color: red; text-align: center; margin-top: 50px;"><h1>Application Mount Error</h1><p>The root element (#root) is missing from index.html.</p></div>';
}
