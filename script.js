const tabs = Array.from(document.querySelectorAll('.op-tab'));
const panels = Array.from(document.querySelectorAll('.op-panel'));

function activateStep(index) {
  tabs.forEach((tab, i) => {
    tab.classList.toggle('active', i === index);
    tab.setAttribute('aria-selected', i === index ? 'true' : 'false');
  });

  panels.forEach((panel, i) => {
    panel.classList.toggle('active', i === index);
  });
}

tabs.forEach((tab) => {
  tab.addEventListener('click', () => {
    const idx = Number(tab.dataset.step);
    activateStep(idx);
  });
});

activateStep(0);

const revealEls = Array.from(document.querySelectorAll('.reveal'));

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.16 }
);

revealEls.forEach((el, idx) => {
  el.style.transitionDelay = `${Math.min(idx * 60, 320)}ms`;
  observer.observe(el);
});
