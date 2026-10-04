(() => {
  const board = document.getElementById("roadmap-board");
  const wrap = document.getElementById("roadmap-wrap");
  if (!board) return;

  const nodes = [...board.querySelectorAll(".roadmap-node")];
  const edges = [...board.querySelectorAll(".roadmap-edge")];
  const ROOT = "Arrays & Hashing";
  let scale = 1;

  const parents = new Map();
  edges.forEach((edge) => {
    const from = edge.dataset.from;
    const to = edge.dataset.to;
    if (!parents.has(to)) parents.set(to, []);
    parents.get(to).push(from);

    const length = edge.getTotalLength();
    edge.dataset.length = String(length);
    edge.style.strokeDasharray = String(length);
    edge.style.strokeDashoffset = "0";
  });

  function setScale(next) {
    scale = Math.min(1.35, Math.max(0.55, next));
    board.style.transform = `scale(${scale})`;
    board.style.transformOrigin = "top left";
  }

  function pathToRoot(targetName) {
    const activeNodes = new Set([targetName, ROOT]);
    const activeEdges = new Set();
    const stack = [targetName];
    const seen = new Set();

    while (stack.length) {
      const current = stack.pop();
      if (seen.has(current)) continue;
      seen.add(current);
      activeNodes.add(current);

      (parents.get(current) || []).forEach((parent) => {
        activeEdges.add(`${parent}=>${current}`);
        stack.push(parent);
      });
    }

    return { activeNodes, activeEdges };
  }

  function edgeDepth(toName) {
    let depth = 0;
    let cursor = toName;
    const guard = new Set();
    while (cursor && cursor !== ROOT && !guard.has(cursor)) {
      guard.add(cursor);
      const preds = parents.get(cursor) || [];
      if (!preds.length) break;
      cursor = preds[0];
      depth += 1;
    }
    return depth;
  }

  function clearHighlight() {
    board.classList.remove("is-tracing");
    nodes.forEach((node) => node.classList.remove("is-on-path", "is-focus"));
    edges.forEach((edge) => {
      edge.classList.remove("is-on-path");
      edge.style.strokeDashoffset = "0";
      edge.style.animation = "none";
    });
  }

  function highlight(targetName) {
    const { activeNodes, activeEdges } = pathToRoot(targetName);
    board.classList.add("is-tracing");

    nodes.forEach((node) => {
      const name = node.dataset.name;
      node.classList.toggle("is-on-path", activeNodes.has(name));
      node.classList.toggle("is-focus", name === targetName);
    });

    const ordered = edges
      .filter((edge) => activeEdges.has(`${edge.dataset.from}=>${edge.dataset.to}`))
      .sort((a, b) => edgeDepth(a.dataset.to) - edgeDepth(b.dataset.to));

    edges.forEach((edge) => {
      if (!activeEdges.has(`${edge.dataset.from}=>${edge.dataset.to}`)) {
        edge.classList.remove("is-on-path");
        edge.style.animation = "none";
        edge.style.strokeDashoffset = "0";
      }
    });

    ordered.forEach((edge, index) => {
      const length = edge.dataset.length;
      edge.classList.add("is-on-path");
      edge.style.strokeDasharray = length;
      edge.style.strokeDashoffset = length;
      edge.style.animation = "none";
      void edge.getBoundingClientRect();
      edge.style.animation = `roadmap-draw 0.38s ease ${index * 55}ms forwards`;
    });
  }

  nodes.forEach((node) => {
    node.addEventListener("mouseenter", () => highlight(node.dataset.name));
    node.addEventListener("focus", () => highlight(node.dataset.name));
  });

  board.addEventListener("mouseleave", clearHighlight);
  board.addEventListener("focusout", (event) => {
    if (!board.contains(event.relatedTarget)) clearHighlight();
  });

  const zoomIn = document.getElementById("roadmap-zoom-in");
  const zoomOut = document.getElementById("roadmap-zoom-out");
  const fit = document.getElementById("roadmap-fit");
  if (zoomIn) zoomIn.addEventListener("click", () => setScale(scale + 0.1));
  if (zoomOut) zoomOut.addEventListener("click", () => setScale(scale - 0.1));
  if (fit && wrap) {
    fit.addEventListener("click", () => {
      const available = wrap.clientWidth - 24;
      const next = Math.min(1, available / 1000);
      setScale(next);
      wrap.scrollTo({ left: 0, top: 0 });
    });
  }
})();
