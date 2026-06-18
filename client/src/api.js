const BACKEND_BASE = import.meta.env.VITE_BACKEND_BASE || "http://localhost:8000";
const API_BASE = `${BACKEND_BASE}/api`;

export const streamPage = async (params, onEvent) => {
  const response = await fetch(`${API_BASE}/stream-page`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    throw new Error("Failed to start stream");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    
    let boundary = buffer.indexOf('\n\n');
    while (boundary !== -1) {
      const chunk = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      
      const lines = chunk.split('\n');
      let eventType = 'message';
      let eventData = null;

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith('data: ')) {
          try {
            eventData = JSON.parse(line.slice(6).trim());
          } catch (e) {
            console.error("Failed to parse event data", line);
          }
        }
      }

      if (eventData) {
        onEvent(eventType, eventData);
      }
      
      boundary = buffer.indexOf('\n\n');
    }
  }
};

export const getPage = async (params) => {
  const response = await fetch(`${API_BASE}/page`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(params),
  });
  
  if (!response.ok) {
    throw new Error("Failed to fetch page");
  }
  
  const data = await response.json();
  // Handle relative URLs from backend
  if (data.imageUrl && data.imageUrl.startsWith("/static")) {
    data.imageUrl = `${BACKEND_BASE}${data.imageUrl}`;
  }
  if (data.depthUrl && data.depthUrl.startsWith("/static")) {
    data.depthUrl = `${BACKEND_BASE}${data.depthUrl}`;
  }
  if (data.videoUrl && data.videoUrl.startsWith("/static")) {
    data.videoUrl = `${BACKEND_BASE}${data.videoUrl}`;
  }
  return data;
};

export const analyzePage = async (pageId, visionModel) => {
  const response = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ pageId, visionModel }),
  });

  if (!response.ok) {
    throw new Error("Failed to analyze page");
  }

  return await response.json();
};

export const uploadImage = async (file) => {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error("Failed to upload image");
  }

  const data = await response.json();
  if (data.imageUrl && data.imageUrl.startsWith("/static")) {
    data.imageUrl = `${BACKEND_BASE}${data.imageUrl}`;
  }
  if (data.depthUrl && data.depthUrl.startsWith("/static")) {
    data.depthUrl = `${BACKEND_BASE}${data.depthUrl}`;
  }
  return data;
};

export const uploadPdf = async (file) => {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/upload-pdf`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error("Failed to upload PDF");
  }

  const data = await response.json();
  // Adjust URLs for all extracted pages
  if (data.pages && Array.isArray(data.pages)) {
    data.pages = data.pages.map(page => {
      if (page.imageUrl && page.imageUrl.startsWith("/static")) {
        page.imageUrl = `${BACKEND_BASE}${page.imageUrl}`;
      }
      return page;
    });
  }
  return data;
};
