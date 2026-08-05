# PR-Agent Reviewer Image from Fork

This Dockerfile builds the PR-Agent application from source code instead of using the unverified base image `pragent/pr-agent:0.39.0-github_app`.

## Purpose

This Dockerfile addresses security concerns by ensuring that the reviewer image is built from our audited fork source rather than relying on potentially unverified Docker Hub base images.

## Usage

To build this image:
```bash
docker build -f Dockerfile.review_image -t pragent/pr-agent:github_action_fork .
```

To run:
```bash
docker run pragent/pr-agent:github_action_fork
```