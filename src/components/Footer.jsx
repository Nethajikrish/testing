import { profile } from '../data.js';

export default function Footer() {
  return (
    <footer className="footer">
      <p>© {new Date().getFullYear()} {profile.name}. Built with React.</p>
    </footer>
  );
}
