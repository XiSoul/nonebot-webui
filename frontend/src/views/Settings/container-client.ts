import { generateURLForWebUI } from "@/client/utils";
import { getAuthToken } from "@/client/auth";

export type ContainerRuntimeSettings = {
  is_docker: boolean;
  proxy_url: string;
  http_proxy: string;
  https_proxy: string;
  all_proxy: string;
  no_proxy: string;
  debian_mirror: string;
  pip_index_url: string;
  pip_extra_index_url: string;
  pip_trusted_host: string;
  github_proxy_base_url: string;
  bot_http_proxy: string;
  bot_https_proxy: string;
  bot_all_proxy: string;
  bot_no_proxy: string;
  bot_proxy_protocol: string;
  bot_proxy_host: string;
  bot_proxy_port: string;
  bot_proxy_username: string;
  bot_proxy_password: string;
  bot_proxy_apply_target: string;
  bot_proxy_instances: string;
};

export type ContainerRuntimeConnectivityItem = {
  name: string;
  target: string;
  ok: boolean;
  skipped: boolean;
  status_code: number;
  elapsed_ms: number;
  error: string;
};

export type ContainerRuntimeConnectivityResponse = {
  ok: boolean;
  results: ContainerRuntimeConnectivityItem[];
};

export type ContainerRuntimeTestMode = "quick" | "deep";

export type ContainerRuntimePresetBenchmarkItem = {
  preset_id: string;
  preset_name: string;
  ok: boolean;
  score_ms: number;
  debian_elapsed_ms: number;
  pip_elapsed_ms: number;
  error: string;
};

export type ContainerRuntimePresetBenchmarkResponse = {
  results: ContainerRuntimePresetBenchmarkItem[];
};

export type ContainerRuntimeProfile = Omit<ContainerRuntimeSettings, "is_docker"> & {
  name: string;
};

export type ContainerRuntimeProfileListResponse = {
  profiles: ContainerRuntimeProfile[];
};

type GenericResponse<T> = {
  detail: T;
};

const getAuthHeaders = () => {
  const token = getAuthToken();
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
};

const parseErrorMessage = async (response: Response) => {
  try {
    const json = await response.json();
    if (typeof json?.detail === "string") return json.detail;
    if (Array.isArray(json?.detail)) return JSON.stringify(json.detail);
  } catch {
    // ignore json parse errors
  }
  return `${response.status} ${response.statusText}`;
};

export const getContainerRuntimeSettings = async () => {
  const url = generateURLForWebUI("/v1/system/container/runtime");
  const response = await fetch(url, {
    method: "GET",
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    return { error: await parseErrorMessage(response), data: undefined };
  }

  const data = (await response.json()) as GenericResponse<ContainerRuntimeSettings>;
  return { data: data.detail, error: undefined };
};

export const updateContainerRuntimeSettings = async (
  data: Omit<ContainerRuntimeSettings, "is_docker">
) => {
  const url = generateURLForWebUI("/v1/system/container/runtime");
  const response = await fetch(url, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    return { error: await parseErrorMessage(response), data: undefined };
  }

  return { data: true, error: undefined };
};

export const testContainerRuntimeSettings = async (
  data: Omit<ContainerRuntimeSettings, "is_docker">,
  mode: ContainerRuntimeTestMode = "quick"
) => {
  const url = generateURLForWebUI("/v1/system/container/runtime/test");
  const response = await fetch(url, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ ...data, mode }),
  });

  if (!response.ok) {
    return { error: await parseErrorMessage(response), data: undefined };
  }

  const json =
    (await response.json()) as GenericResponse<ContainerRuntimeConnectivityResponse>;
  return { data: json.detail, error: undefined };
};

export const benchmarkContainerRuntimePresets = async (
  proxy: Pick<
    Omit<ContainerRuntimeSettings, "is_docker">,
    "proxy_url" | "no_proxy"
  >
) => {
  const url = generateURLForWebUI("/v1/system/container/runtime/preset/benchmark");
  const response = await fetch(url, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(proxy),
  });

  if (!response.ok) {
    return { error: await parseErrorMessage(response), data: undefined };
  }

  const json =
    (await response.json()) as GenericResponse<ContainerRuntimePresetBenchmarkResponse>;
  return { data: json.detail, error: undefined };
};

export const getContainerRuntimeProfiles = async () => {
  const url = generateURLForWebUI("/v1/system/container/runtime/profile/list");
  const response = await fetch(url, {
    method: "GET",
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    return { error: await parseErrorMessage(response), data: undefined };
  }

  const json =
    (await response.json()) as GenericResponse<ContainerRuntimeProfileListResponse>;
  return { data: json.detail.profiles, error: undefined };
};

export const saveContainerRuntimeProfile = async (
  name: string,
  data: Omit<ContainerRuntimeSettings, "is_docker">
) => {
  const url = generateURLForWebUI("/v1/system/container/runtime/profile/save");
  const response = await fetch(url, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ name, ...data }),
  });

  if (!response.ok) {
    return { error: await parseErrorMessage(response), data: undefined };
  }

  return { data: true, error: undefined };
};

export const applyContainerRuntimeProfile = async (name: string) => {
  const url = generateURLForWebUI("/v1/system/container/runtime/profile/apply");
  const response = await fetch(url, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ name }),
  });

  if (!response.ok) {
    return { error: await parseErrorMessage(response), data: undefined };
  }

  return { data: true, error: undefined };
};

export const deleteContainerRuntimeProfile = async (name: string) => {
  const encodedName = encodeURIComponent(name);
  const url = generateURLForWebUI(
    `/v1/system/container/runtime/profile/delete?name=${encodedName}`
  );
  const response = await fetch(url, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    return { error: await parseErrorMessage(response), data: undefined };
  }

  return { data: true, error: undefined };
};
