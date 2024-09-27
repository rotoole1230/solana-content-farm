import os
import time
from groq import Groq
import git

# Initialize the Groq client with your API key
client = Groq(
    api_key="GROQ_API_KEY",
)

# Path to the content directory in your static site repository
CONTENT_DIR = 'solana-content-farm/articles'

# Initialize Git repository
repo = Repo('path/to/your/site')

# Agent 1: Topic Generator Agent
def topic_generator_agent():
    prompt = "Generate a list of 10 unique, in-depth article topics that explore detailed and technical aspects of the Solana blockchain. The topics should cover different areas to ensure comprehensive coverage."
    response = client.chat.completions.create(
        messages=[
            {"role": "user", "content": prompt}
        ],
        model="llama-3.2-90b-text-preview",
    )
    topics = response.choices[0].message.content
    # Process topics into a list
    topics_list = [topic.strip("- ").strip() for topic in topics.split('\n') if topic.strip()]
    return topics_list

# Agent 2: Writer Agent
def writer_agent(topic):
    prompt = f"Write a detailed and technical article about the following topic:\n{topic}\nThe article should be comprehensive, well-structured, and informative."
    response = client.chat.completions.create(
        messages=[
            {"role": "user", "content": prompt}
        ],
        model="llama-3.2-90b-text-preview",
    )
    article = response.choices[0].message.content
    return article

# Agent 3: SEO Agent
def seo_agent(article):
    prompt = f"Optimize the following article for SEO. Include relevant keywords, meta descriptions, and ensure it adheres to best SEO practices:\n\n{article}"
    response = client.chat.completions.create(
        messages=[
            {"role": "user", "content": prompt}
        ],
        model="llama-3.2-90b-text-preview",
    )
    optimized_article = response.choices[0].message.content
    return optimized_article

# Agent 4: Front-End Agent
def front_end_agent(article_content, title):
    # Generate a filename based on the title
    filename = title.lower().replace(' ', '-').replace('/', '-') + '.md'
    filepath = os.path.join(CONTENT_DIR, filename)
    
    # Create front matter for the Markdown file
    front_matter = f"""---
title: "{title}"
date: "{time.strftime('%Y-%m-%d')}"
---

"""
    # Combine front matter and article content
    full_content = front_matter + article_content
    
    # Write the content to a Markdown file
    with open(filepath, 'w', encoding='utf-8') as file:
        file.write(full_content)
    
    print(f"Article '{title}' has been saved to {filepath}")
    return filepath

# Agent 5: Deployment Agent
def deployment_agent(filepaths):
    # Add new files to Git
    repo.index.add(filepaths)
    # Commit changes
    repo.index.commit("Add new articles")
    # Push to remote repository
    origin = repo.remote(name='origin')
    origin.push()
    print("Changes have been pushed to the repository.")

# Main orchestration function
def main():
    # Endless loop to create an endless funnel of content
    while True:
        topics = topic_generator_agent()
        filepaths = []
        for topic in topics:
            print(f"Processing topic: {topic}\n")
            article = writer_agent(topic)
            optimized_article = seo_agent(article)
            filepath = front_end_agent(optimized_article, title=topic)
            filepaths.append(filepath)
            # Optional: Add a delay between processing each topic
            time.sleep(2)  # Sleep for 2 seconds
        # Deploy the new articles
        deployment_agent(filepaths)
        # Optional: Sleep before generating new topics
        time.sleep(600)  # Sleep for 10 minutes before generating new topics

# Run the main function
if __name__ == "__main__":
    main()

