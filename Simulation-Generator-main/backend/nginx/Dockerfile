FROM nginx:1.27-alpine

RUN rm /etc/nginx/conf.d/default.conf
COPY backend/nginx/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
