import { projects } from '../data.js';

export default function Projects() {
  return (
    <section id="projects" className="section section-alt">
      <div className="container">
        <h2 className="section-title">Projects</h2>
        <div className="project-grid">
          {projects.map((project) => (
            <article key={project.title} className="card">
              <h3>{project.title}</h3>
              <p>{project.description}</p>
              <ul className="tags">
                {project.tags.map((tag) => (
                  <li key={tag} className="tag">{tag}</li>
                ))}
              </ul>
              <div className="card-links">
                <a href={project.link} target="_blank" rel="noreferrer">Live demo</a>
                <a href={project.repo} target="_blank" rel="noreferrer">Source</a>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
