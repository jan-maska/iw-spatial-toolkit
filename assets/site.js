(() => {
  const config = window.IW_SITE_CONFIG || {};
  const links = {
    docs: config.docsUrl,
    download: config.downloadUrl,
    github: config.githubUrl
  };

  document.querySelectorAll("[data-link]").forEach((anchor) => {
    const destination = links[anchor.dataset.link];
    if (!destination) return;
    anchor.href = destination;
    if (/^https?:\/\//i.test(destination)) {
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
    }
  });

  document.querySelectorAll("[data-year]").forEach((node) => {
    node.textContent = new Date().getFullYear();
  });

  const header = document.querySelector("[data-header]");
  const toggle = document.querySelector("[data-nav-toggle]");
  const nav = document.querySelector("[data-nav]");

  const closeNav = () => {
    if (!toggle || !nav) return;
    toggle.setAttribute("aria-expanded", "false");
    nav.classList.remove("is-open");
  };

  toggle?.addEventListener("click", () => {
    const open = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!open));
    nav?.classList.toggle("is-open", !open);
  });

  nav?.querySelectorAll("a").forEach((anchor) => anchor.addEventListener("click", closeNav));
  window.addEventListener("resize", () => {
    if (window.innerWidth > 820) closeNav();
  });

  const syncHeader = () => header?.classList.toggle("is-scrolled", window.scrollY > 16);
  syncHeader();
  window.addEventListener("scroll", syncHeader, { passive: true });

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const revealNodes = [...document.querySelectorAll("[data-reveal]")];
  if (reducedMotion || !("IntersectionObserver" in window)) {
    revealNodes.forEach((node) => node.classList.add("is-visible"));
  } else {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.12 });
    revealNodes.forEach((node) => observer.observe(node));
  }
})();
