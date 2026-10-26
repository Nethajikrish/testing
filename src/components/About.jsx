import { experience, profile, skills } from '../data.js';

export default function About() {
  return (
    <section id="about" className="section">
      <div className="container">
        <h2 className="section-title">About Me</h2>
        <p className="about-text">{profile.bio}</p>
        <h3 className="subheading">Experience</h3>
        <ul className="timeline">
          {experience.map((job) => (
            <li key={`${job.company}-${job.period}`} className="timeline-item">
              <p className="timeline-period">{job.period}</p>
              <h4>{job.role}</h4>
              <p className="timeline-company">{job.company}</p>
              <p>{job.summary}</p>
            </li>
          ))}
        </ul>
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
