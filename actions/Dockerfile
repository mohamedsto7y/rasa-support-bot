# Action server. Build context is this folder.
FROM rasa/rasa-sdk:3.6.2

WORKDIR /app
USER root
RUN pip install --no-cache-dir requests
COPY . ./actions
USER 1001

EXPOSE 5055
ENTRYPOINT ["python", "-m", "rasa_sdk"]
CMD ["--actions", "actions", "--port", "5055"]
