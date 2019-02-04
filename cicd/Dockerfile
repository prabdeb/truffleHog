FROM python:3-alpine
RUN apk add --no-cache git && pip install trufflehog xlsxwriter requests
WORKDIR /proj
COPY scan.py /proj/scan.py
ENTRYPOINT [ "python", "/proj/scan.py" ]