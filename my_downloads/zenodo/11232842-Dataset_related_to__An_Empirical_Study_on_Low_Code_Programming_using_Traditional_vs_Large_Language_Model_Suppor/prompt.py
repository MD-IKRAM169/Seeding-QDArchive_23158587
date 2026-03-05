import openai

user_role_str = """
You are an expert in the field of software engineering.

The definition of low code programming is as follows:
Complies with any of the following three technologies, meets the definition of "low code programming": visual programming languages, programming by demonstration, and programming by natural language.

The current popular large language models or AI code generation tools include chatGPT, GPT, Bard, Claude, CodeX, copilot, etc.
The current advanced "programming by natural language" technology uses large language models or AI code generation tools to generate code.

The following are some examples of using 'programming by natural language':
1. Directly or indirectly using large language models or AI code generation tools to solve programming problems such as web, page, algorithm,software application problems, etc.
2. Directly or indirectly using large language models or AI code generation tools to generate code.
3.. Communicate directly or indirectly with large language models or AI code generation tools to solve problems such as web, algorithm, math, and software application development.

Based on the above definition of "low code programming", determine whether the following input statements involve "low code programming". The input statement is the discussion of people on the forum. Please analyze each sentence sentence by sentence and output the analysis result. As long as some of these statements refer to "programming by natural language," even if it meets the standard.

The input statements are as follow:
"""

assistant_str = """
I understand the criteria you've provided for determining whether a statement qualifies as "low code programming." Based on your definition, I will evaluate the input statement provided. Please provide the specific input statement you would like me to analyze in the format you mentioned: {"result": "True/False", "reason": "Because..."}
"""

format_statement = """
According to the result of the above statement by statement, as long as there is a "programming by natural languate", output "True". Otherwise output "False".

Just output "True" or "False", Do not output other statements.
"""

example_input = """
I want to make a video and movie player. I am using the blob urls in a react function. I have used Chat-GPT to generate that function because I don't have much knowledge of JavaScript. 
"""
example_output = """
Analysis:

1. "I want to make a video and movie player." - This sentence indicates the desire to create a video and movie player, but does not mention programming or natural language.

2. "I am using the blob urls in a react function." - This sentence mentions the usage of blob URLs in a React function, which involves programming but not natural language.

3. "I have used Chat-GPT to generate that function because I don't have much knowledge of JavaScript." - This sentence explicitly mentions the use of Chat-GPT, a large language model, to generate a function. This involves programming by natural language.
In conclusion, the input statement contains one sentence that involves "programming by natural language."
"""

input = ""

response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[
        {"role": "user", "content": user_role_str + example_input},
        {"role": "assistant", "content": example_output},
        # {"role": "user", "content": df.loc[idx, 'comment']},
        {"role": "user", "content": """
        The input statements are as follow:"{}"
        """.format(input)},
    ]
)
response_str1 = response["choices"][0].message["content"]

response2 = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[
        {"role": "user", "content": user_role_str + example_input},
        {"role": "assistant", "content": example_output},
        {"role": "user", "content": """
        The input statements are as follow:"{}"
        """.format(input)},
        # {"role": "assistant", "content": response_str1},
        {"role": "assistant", "content": response_str1},
        {"role": "user", "content": format_statement},
    ]
)