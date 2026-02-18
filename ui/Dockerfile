FROM nginx:alpine

# Copy HTML and JS files
COPY index.html /usr/share/nginx/html/index.html
COPY DrupalMindUI.jsx /usr/share/nginx/html/DrupalMindUI.jsx
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
