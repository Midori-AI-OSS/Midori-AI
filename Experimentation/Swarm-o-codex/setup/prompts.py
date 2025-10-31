
from agents import Agent
from agents import ModelSettings
from agents import OpenAIResponsesModel
from agents import OpenAIChatCompletionsModel
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX

def setup_agents(model: OpenAIChatCompletionsModel | OpenAIResponsesModel, base_model_settings: ModelSettings) -> list[Agent]:
    #### These are the models persona files, They are read on load, feel free to edit them
    start_prompt = RECOMMENDED_PROMPT_PREFIX + open('personas/META_PROMPT.md').read()
    coder_prompt = start_prompt + open('personas/CODER.md').read()
    auditor_prompt = start_prompt + open('personas/AUDITOR.md').read()
    manager_prompt = start_prompt + open('personas/MANAGER.md').read()
    reviewer_prompt = start_prompt + open('personas/REVIEWER.md').read()
    task_master_prompt = start_prompt + open('personas/TASKMASTER.md').read()
    storyteller_prompt = start_prompt + open('personas/STORYTELLER.md').read()

    #### These are the agent objs, they tell the system what agents are in the swarm
    coder_agent = Agent(name="Coder", instructions=coder_prompt, model=model, model_settings=base_model_settings)
    auditor_agent = Agent(name="Auditor", instructions=auditor_prompt, model=model, model_settings=base_model_settings)
    manager_agent = Agent(name="Manager", instructions=manager_prompt, model=model, model_settings=base_model_settings)
    reviewer_agent = Agent(name="Reviewer", instructions=reviewer_prompt, model=model, model_settings=base_model_settings)
    task_master_agent = Agent(name="Task Master", instructions=task_master_prompt, model=model, model_settings=base_model_settings)
    storyteller_agent = Agent(name="Storyteller", instructions=storyteller_prompt, model=model, model_settings=base_model_settings)

    #### if you add a agent to the swarm it needs to be added here so that the other agents can "pass the mic" to it
    handoffs: list[Agent] = []
    handoffs.append(coder_agent)
    handoffs.append(auditor_agent)
    handoffs.append(manager_agent)
    handoffs.append(reviewer_agent)
    handoffs.append(task_master_agent)
    handoffs.append(storyteller_agent)

    return handoffs

def setup_summary_agent(model: OpenAIChatCompletionsModel | OpenAIResponsesModel, base_model_settings: ModelSettings) -> Agent:
    base_model_settings.temperature = 0.1
    starter_prompt: str = "Summarize the conversation context in 5-10 sentences."
    prompt: str = f"{starter_prompt} Focus on: The request the user made, completed tasks, tool outputs, and handoff reasons. Be extremely concise."
    summarizer_agent: Agent = Agent(name="ContextSummarizer", instructions=prompt, model=model, model_settings=base_model_settings)
    return summarizer_agent