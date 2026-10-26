import { profile } from '../data.js';

export default function Hero() {
  return (
    <section id="top" className="hero">
      <div className="container">
        <p className="hero-greeting">Hi, I'm</p>
        <h1>{profile.name}</h1>
        <h2>{profile.title}</h2>
        <p className="hero-bio">{profile.bio}</p>
        <div className="hero-actions">
          <a href="#projects" className="btn btn-primary">View my work</a>
          <a href="#contact" className="btn btn-outline">Contact me</a>
        </div>
      </div>
    </section>
  );
}
