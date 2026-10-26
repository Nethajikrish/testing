import { profile, skills } from '../data.js';

export default function About() {
  return (
    <section id="about" className="section">
      <div className="container">
        <h2 className="section-title">About Me</h2>
        <p className="about-text">{profile.bio}</p>
        <h3 className="subheading">Skills</h3>
        <ul className="skills">
          {skills.map((skill) => (
            <li key={skill} className="skill">{skill}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}
