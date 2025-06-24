import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.tsx';
import './index.css';

const rootElement = document.getElementById('root');
console.log(rootElement);
if (!rootElement) {
  console.error('Root element with id="root" not found!');
  document.body.innerHTML = '<div style="color:red;font-size:2rem;text-align:center;margin-top:2rem;">Root element with id="root" not found!</div>';
} else {
  createRoot(rootElement).render(
    <StrictMode>
      <App />
    </StrictMode>
  );
}
