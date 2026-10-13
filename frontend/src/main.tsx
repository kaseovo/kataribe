import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import './index.css';
import App from './App.tsx';
import Family from './Family.tsx';
import Landing from './Landing.tsx';
import Talk from './Talk.tsx';

// Four audiences, four pages. A stranger arrives at the start page, the family
// at a link to one person, the senior at a screen of their own, and the team at
// the console, which none of the others should ever see. A router would be more
// than this needs.
const path = window.location.pathname;
const family = path.match(/^\/family\/([\w-]+)/);
const talk = path.match(/^\/talk\/([\w-]+)/);
const team = /^\/console\/?$/.test(path);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {family ? (
      <Family seniorId={family[1]} />
    ) : talk ? (
      <Talk seniorId={talk[1]} />
    ) : team ? (
      <App />
    ) : (
      <Landing />
    )}
  </StrictMode>,
);
