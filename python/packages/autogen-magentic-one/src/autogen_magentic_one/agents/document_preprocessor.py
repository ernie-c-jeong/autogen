import os
import re
from typing import Tuple, Union

import requests

from autogen_core.base import CancellationToken
from autogen_core.components import default_subscription
from autogen_core.components.models import (
    UserMessage,
)

from ..messages import UserContent
from ..utils import message_content_to_str
from .base_worker import BaseWorker



@default_subscription
class DocumentPreprocessor(BaseWorker):
    DEFAULT_DESCRIPTION = """
I am a specialized AI assistant for preprocessing PDF files and converting them into JSON format. However, when giving me instructions, you must first use **FileSurfer** to check whether the PDF file exists and include the PDF file's path in the instructions.

File paths must be enclosed within `<FilePath></FilePath>` tags, with one file path per line.

Example:

```
<FilePath>
File Path 1
File Path 2
...
</FilePath>
```
"""
    def __init__(
        self,
        description: str = DEFAULT_DESCRIPTION,
        check_last_n_message: int = 5,
        # *,
        # executor: CodeExecutor,
        # confirm_execution: ConfirmCode | Literal["ACCEPT_ALL"],
    ) -> None:
        super().__init__(description)
        # self._executor = executor
        self._check_last_n_message = check_last_n_message
        # self._confirm_execution = confirm_execution

    async def _generate_reply(self, cancellation_token: CancellationToken) -> Tuple[bool, UserContent]:
        """Respond to a reply request."""

        n_messages_checked = 0
        for idx in range(len(self._chat_history)):
            message = self._chat_history[-(idx + 1)]

            if not isinstance(message, UserMessage):
                continue

            # Extract code block from the message.
            code = self._extract_file_paths(message_content_to_str(message.content))
            print(f"Provided file paths are: {code}")

            # 2. 코드 실행
            if code is not None and code != []:
                result = ""
                for file_path in code:
                    result += self.preprocess_document(file_path)
                    result += '\n'

                return (False, result) # File surfer로 파일 제대로 있는지 체크하기 위해 False 반환함.
            else:
                n_messages_checked += 1
                if n_messages_checked > self._check_last_n_message:
                    break

        return (
            False,
            """
File path information was not included.
To use FileSurfer to determine if a PDF file exists, you must include the path to the PDF file in the directive.
When passing file paths, they must be enclosed in <FilePath></FilePath> tags, and one path must be passed per line.

Example)

<FilePath>
FilePath 1
FilePath 2
...

</FilePath>
""",
        )

    ### 첫번째 code block을 찾음
    def _extract_execution_request(self, markdown_text: str) -> Union[Tuple[str, str], None]:
        pattern = r"```(\w+)\n(.*?)\n```"
        # Search for the pattern in the markdown text
        match = re.search(pattern, markdown_text, re.DOTALL)
        # Extract the language and code block if a match is found
        if match:
            return (match.group(1), match.group(2))
        return None

    def _extract_file_paths(self, input_data):
        # 정규 표현식으로 <FilePath>와 </FilePath> 사이의 내용을 추출
        file_path_block = re.search(r"<FilePath>(.*?)</FilePath>", input_data, re.DOTALL)

        if file_path_block:
            # 태그 안의 내용을 가져옴
            content = file_path_block.group(1).strip()
            # 개행을 기준으로 분리하여 리스트 생성
            file_paths = [line.strip() for line in content.splitlines() if line.strip()]
            return file_paths
        else:
            return None
        
    def preprocess_document(self, file_path: str):
        # Check if the file exists
        if not os.path.exists(file_path):
            return (f"'{file_path}' not found.")

        # Step 3: Prepare the POST request data
        with open(file_path, 'rb') as pdf_file:
            file_name = os.path.basename(file_path)
            request_data = {
                'uploadFiles': (file_name, pdf_file, 'multipart/form-data')
            }

            # Step 4: Send the request
            # response = requests.post('http://192.168.17.143:8200/v1/preprocess/document', files=request_data)
            response = requests.post('http://192.168.17.149:8200/v1/preprocess/document', files=request_data)

        # Check if the request was successful
        if response.status_code == 200:
            # Step 5: Save the response to a JSON file
            # output_json_path = os.path.join(samples_folder, 'output.json')
            output_json_path = "./output.json"

            with open(output_json_path, 'w', encoding='utf-8') as json_file:
                json_file.write(response.text)

            return(f"""The processed JSON has been saved to '{output_json_path}'.""")
            # """
            # ``` json
            # {response.text}
            # ```
            # """
        else:
            return (f"Failed to process the document. Status code: {response.status_code}, Response: {response.text}")
