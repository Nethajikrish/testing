import { profile } from '../data.js';

export default function Contact() {
  return (
    <section id="contact" className="section">
      <div className="container contact">
        <h2 className="section-title">Get In Touch</h2>
        <p>
          I'm open to new opportunities and collaborations. Feel free to reach out.
        </p>
        <a href={`mailto:${profile.email}`} className="btn btn-primary">
          {profile.email}
        </a>
        <div className="social">
          <a href={profile.github} target="_blank" rel="noreferrer">GitHub</a>
          <a href={profile.linkedin} target="_blank" rel="noreferrer">LinkedIn</a>
        </div>
      </div>
    </section>
  );
}
