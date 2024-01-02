import json
from datetime import datetime
from .utils import ComponentABC
from Agently.utils import RuntimeCtxNamespace

class Tool(ComponentABC):
    def __init__(self, agent: object):
        self.agent = agent
        self.is_debug = self.agent.settings.get_trace_back("is_debug")
        self.settings = RuntimeCtxNamespace("plugin_settings.agent_component.Tool", self.agent.settings)
        self.tool_manager = self.agent.tool_manager
        self.tool_dict = {}
        self.register_tool = self.tool_manager.register
        self.call_tool_func = self.tool_manager.call_tool_func
        self.set_tool_proxy = self.tool_manager.set_tool_proxy

    def add_public_tools(self, tool_name_list: (str, list)):
        if isinstance(tool_name_list, str):
            tool_name_list = [tool_name_list]
        for tool_name in tool_name_list:
            tool_info = self.tool_manager.get_tool_info(tool_name, with_args=True)
            if tool_info:
                self.tool_dict.update({ tool_name: tool_info })
        return self.agent

    def add_public_categories(self, tool_category_list: (str, list)):
        if isinstance(tool_category_list, str):
            tool_category_list = [tool_category_list]
        tool_dict = self.tool_manager.get_tool_dict(categories=tool_category_list, with_args=True)
        for key, value in tool_dict.items():
            self.tool_dict.update({ key: value })
        return self.agent

    def add_all_public_tools(self):
        all_tool_dict = self.tool_manager.get_tool_dict(with_args=True)
        for key, value in all_tool_dict.items():
            self.tool_dict.update({ key: value })
        return self.agent

    def _prefix(self):
        if len(self.tool_dict.keys()) > 0:
            if self.is_debug:
                print("[Agent Component] Using Tools: Start tool using judgement...")
            tool_list = []
            for tool_name, tool_info in self.tool_dict.items():
                tool_list.append(tool_info)
            result = (
                self.agent.worker_request
                    .input({
                        "target": self.agent.request.request_runtime_ctx.get("prompt")
                    })
                    .info("current date", datetime.now().date())
                    .info("tools", json.dumps(tool_list))
                    .instruct("make plans to achieve {input.target}.\n * if use search tool, choose ONLY ONE SEARCH TOOL THAT FIT MOST.")
                    .output({
                        "plans": [{
                            "step_goal": ("String", "brief goal of this step"),
                            "using_tool": (
                                {
                                    "tool_name": ("String", "{tool_name} from {tools}"),
                                    "args": ("according {args} requirement in {tools}", ),
                                },
                                "output Null if do not need to use tool"
                            ),
                        }],
                    })
                    .start()
            )
            tool_results = {}
            for step in result["plans"]:
                if "using_tool" in step and isinstance(step["using_tool"], dict) and "tool_name" in step["using_tool"]:
                    if self.is_debug:
                        print("[Using Tool]: ", step["using_tool"])
                    tool_info = self.tool_manager.get_tool_info(step["using_tool"]["tool_name"], full=True)
                    if tool_info:
                        tool_kwrags = step["using_tool"]["args"] if "args" in step["using_tool"] and isinstance(step["using_tool"]["args"], dict) else {}
                        if tool_info["require_proxy"]:
                            proxy = self.agent.settings.get_trace_back("proxy")
                            if proxy == None:
                                proxy = self.agent.tool_manager.get_tool_proxy()
                            if proxy:
                                tool_kwrags.update({ "proxy": proxy })
                        call_result = None
                        try:
                            call_result = self.call_tool_func(
                                tool_info["tool_name"],
                                **tool_kwrags
                            )
                        except Exception as e:
                            if self.is_debug:
                                print("[Tool Error]: ", e)
                        if call_result:
                            info_key = json.dumps(step["step_goal"])
                            info_value = call_result["for_agent"] if isinstance(call_result, dict) and "for_agent" in call_result else call_result
                            tool_results[info_key] = info_value
                            if self.is_debug:
                                print("[Result]: ", info_key, info_value)
                    else:
                        if self.is_debug:
                            print(f"[Result]: Can not find tool '{ step['using_tool']['tool_name'] }'")
            if len(tool_results.keys()) > 0:
                return {
                    "information": tool_results
                }
            else:
                return None
        else:
            return None

    def export(self):
        return {
            "prefix": self._prefix,
            "suffix": None,
            "alias": {
                "register_tool": { "func": self.register_tool },
                "call_tool": { "func": self.call_tool_func },
                "set_tool_proxy": { "func": self.set_tool_proxy },
                "add_public_tools": { "func": self.add_public_tools },
                "add_public_categories": { "func": self.add_public_categories },
                "add_all_public_tools": { "func": self.add_all_public_tools }
            }
        }

def export():
    return ("Tool", Tool)