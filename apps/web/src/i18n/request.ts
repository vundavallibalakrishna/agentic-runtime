import { getRequestConfig } from "next-intl/server";

import messages from "../messages/en.json";

export default getRequestConfig(() => ({
  locale: "en",
  timeZone: "UTC",
  messages,
}));
