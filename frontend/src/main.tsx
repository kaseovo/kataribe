import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import './index.css';
import App from './App.tsx';
import Family from './Family.tsx';
import Talk from './Talk.tsx';

// Three audiences, three pages. The family arrives at a link to one person,
// the senior has a screen of their own, and neither should ever see the tuning
// console. A router would be more than this needs.
const path = window.location.pathname;
const family = path.match(/^\/family\/([\w-]+)/);
const talk = path.match(/^\/talk\/([\w-]+)/);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {family ? <Family seniorId={family[1]} /> : talk ? <Talk seniorId={talk[1]} /> : <App />}
  </StrictMode>,
);
