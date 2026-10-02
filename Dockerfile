# Rasa server. The model is trained at build time so the image is self-contained.
FROM rasa/rasa:3.6.20-full

WORKDIR /app
COPY --chown=1001 config.yml domain.yml credentials.yml endpoints*.yml ./
COPY --chown=1001 data ./data
RUN rasa train --fixed-model-name model --out models

EXPOSE 5005
# The image's ENTRYPOINT is `rasa`.
CMD ["run", "--enable-api", "--cors", "*", "--port", "5005", \
     "--model", "models/model.tar.gz", "--endpoints", "endpoints.cloudrun.yml"]
