from importlib import import_module

_EXPORTS = {
    "nisb_room_shared_whoami": (".tools", "nisb_room_shared_whoami"),
    "nisb_room_shared_create": (".tools", "nisb_room_shared_create"),
    "nisb_room_shared_list": (".tools", "nisb_room_shared_list"),
    "nisb_room_get_info": (".tools", "nisb_room_get_info"),
    "nisb_room_update_info": (".tools", "nisb_room_update_info"),
    "nisb_room_get_state": (".tools", "nisb_room_get_state"),
    "nisb_room_update_state": (".tools", "nisb_room_update_state"),
    "nisb_room_revoke_federated_member_access": (".tools", "nisb_room_revoke_federated_member_access"),
    "nisb_room_role_list": (".room_tools_roles", "nisb_room_role_list"),
    "nisb_room_role_create": (".room_tools_roles", "nisb_room_role_create"),
    "nisb_room_role_update": (".room_tools_roles", "nisb_room_role_update"),
    "nisb_room_role_delete": (".room_tools_roles", "nisb_room_role_delete"),
    "nisb_room_mcp_provider_list": (".tools", "nisb_room_mcp_provider_list"),
    "nisb_room_mcp_provider_share_ref_resolve": (".tools", "nisb_room_mcp_provider_share_ref_resolve"),
    "nisb_room_mcp_share_ref_issue": (".tools", "nisb_room_mcp_share_ref_issue"),
    "nisb_room_mcp_publication_get": (".tools", "nisb_room_mcp_publication_get"),
    "nisb_room_mcp_grant_list": (".tools", "nisb_room_mcp_grant_list"),
    "nisb_room_mcp_grant_revoke": (".tools", "nisb_room_mcp_grant_revoke"),
    "nisb_room_mcp_provider_call": (".tools", "nisb_room_mcp_provider_call"),
    "nisb_room_mcp_external_provider_list": (".room_mcp_external_export", "nisb_room_mcp_external_provider_list"),
    "nisb_room_mcp_external_provider_call": (".room_mcp_external_export", "nisb_room_mcp_external_provider_call"),
    "nisb_room_mcp_external_publish_get": (".room_tools_external_mcp_publish", "nisb_room_mcp_external_publish_get"),
    "nisb_room_mcp_external_publish_enable": (".room_tools_external_mcp_publish", "nisb_room_mcp_external_publish_enable"),
    "nisb_room_mcp_external_publish_revoke": (".room_tools_external_mcp_publish", "nisb_room_mcp_external_publish_revoke"),
    "nisb_room_mcp_external_publish_regenerate": (".room_tools_external_mcp_publish", "nisb_room_mcp_external_publish_regenerate"),
    "nisb_room_shared_post": (".tools", "nisb_room_shared_post"),
    "nisb_room_shared_provider_post": (".tools", "nisb_room_shared_provider_post"),
    "nisb_room_runtime_stop_current": (".tools", "nisb_room_runtime_stop_current"),
    "nisb_room_runtime_pause_current": (".tools", "nisb_room_runtime_pause_current"),
    "nisb_room_runtime_resume_from_checkpoint": (".tools", "nisb_room_runtime_resume_from_checkpoint"),
    "nisb_room_shared_recent": (".tools", "nisb_room_shared_recent"),
    "nisb_room_events_recent": (".tools", "nisb_room_events_recent"),
    "nisb_room_events_replay": (".tools", "nisb_room_events_replay"),
    "nisb_room_shared_join": (".tools", "nisb_room_shared_join"),
    "nisb_room_workspace_get": (".room_workspace", "nisb_room_workspace_get"),
    "nisb_room_workspace_set": (".room_workspace", "nisb_room_workspace_set"),
    "nisb_room_workspace_clear": (".room_workspace", "nisb_room_workspace_clear"),
    "nisb_room_supervisor_skills_list": (".room_supervisor_skills", "nisb_room_supervisor_skills_list"),
    "nisb_room_save_intent_parse": (".room_save", "nisb_room_save_intent_parse"),
    "nisb_room_save_from_text": (".room_save", "nisb_room_save_from_text"),
}

_LAZY_MODULES = {
    "room_contracts": ".room_contracts",
    "room_packet_builder": ".room_packet_builder",
    "room_runtime_reader": ".room_runtime_reader",
    "room_replay_builder": ".room_replay_builder",
    "room_tools_runtime": ".room_tools_runtime",
    "room_mcp_provider_contract": ".room_mcp_provider_contract",
    "room_mcp_provider_registry": ".room_mcp_provider_registry",
}

__all__ = list(_EXPORTS.keys())


def __getattr__(name):
    module_name = _LAZY_MODULES.get(name)
    if module_name:
        module = import_module(module_name, __name__)
        globals()[name] = module
        return module

    export = _EXPORTS.get(name)
    if export:
        mod_name, attr_name = export
        value = getattr(import_module(mod_name, __name__), attr_name)
        globals()[name] = value
        return value

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals().keys()) | set(__all__) | set(_LAZY_MODULES.keys()))

