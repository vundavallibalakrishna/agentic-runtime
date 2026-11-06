"use client";

import { useTranslations } from "next-intl";

import { EmptyState } from "@/components/common/management-layout";
import { Badge } from "@/components/ui/badge";

import { RowActions, Select, SmallButton, TestLine } from "./parts";
import {
  type Alias,
  type Model,
  modelsFor,
  type Provider,
  type StandardAlias,
  type Tests,
} from "./types";

const CARD = "rounded-xl border border-[var(--border)] bg-[var(--card)]";

/** The names the product asks for, each with the model the tenant pointed it at. */
export function UsesSection({
  standard,
  models,
  canManage,
  advanced,
  tests,
  onPoint,
  onTest,
  onClear,
  onOptions,
}: {
  standard: StandardAlias[];
  models: Model[];
  canManage: boolean;
  advanced: boolean;
  tests: Tests;
  onPoint: (item: StandardAlias, modelId: string) => void;
  onTest: (aliasId: string) => void;
  onClear: (item: StandardAlias) => void;
  onOptions: (aliasId: string) => void;
}) {
  const t = useTranslations("models");
  return (
    <section aria-labelledby="models-uses" className="mb-10">
      <h2 className="text-base font-semibold" id="models-uses">
        {t("usesTitle")}
      </h2>
      <p className="mb-4 mt-1 max-w-2xl text-sm leading-relaxed text-[var(--muted-foreground)]">
        {t("usesBody")}
      </p>
      <ul className={`${CARD} divide-y divide-[var(--border)]`}>
        {standard.map((item) => {
          const choices = modelsFor(item, models);
          const own = item.set && !item.platform;
          return (
            <li className="grid gap-3 p-4 md:grid-cols-[minmax(0,1fr)_16rem]" key={item.alias}>
              <div className="min-w-0">
                <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
                  {t(`uses.${item.alias}.title`)}
                  <code className="text-xs font-normal text-[var(--muted-foreground)]">
                    {item.alias}
                  </code>
                  {item.set ? <Badge>{t("set")}</Badge> : null}
                  {!item.set && item.required ? (
                    <Badge className="border-[var(--destructive)]">{t("notSetRequired")}</Badge>
                  ) : null}
                  {!item.set && !item.required ? (
                    <Badge className="text-[var(--muted-foreground)]">{t("notSet")}</Badge>
                  ) : null}
                  {item.set && item.platform ? <Badge>{t("platform")}</Badge> : null}
                </p>
                <p className="mt-1 text-sm leading-relaxed text-[var(--muted-foreground)]">
                  {t(`uses.${item.alias}.body`)}
                </p>
                {item.aliasId ? <TestLine result={tests[`alias:${item.aliasId}`]} /> : null}
              </div>
              <div className="grid content-start gap-2">
                <Select
                  disabled={!canManage || choices.length === 0}
                  id={`use-${item.alias}`}
                  label={t("modelFor", { use: t(`uses.${item.alias}.title`) })}
                  onChange={(next) => (next ? onPoint(item, next) : undefined)}
                  value={item.modelId ?? ""}
                >
                  <option value="">{t("chooseModel")}</option>
                  {choices.map((model) => (
                    <option key={model.id} value={model.id}>
                      {model.name}
                    </option>
                  ))}
                </Select>
                {choices.length === 0 ? (
                  <p className="text-xs leading-relaxed text-[var(--muted-foreground)]">
                    {item.capability
                      ? t(`needs.${item.capability}`)
                      : t("noModelOfKind", { kind: t(`kindNames.${item.kind}`) })}
                  </p>
                ) : null}
                {item.aliasId ? (
                  <RowActions>
                    <SmallButton
                      disabled={!canManage}
                      label={t("testNamed", { name: t(`uses.${item.alias}.title`) })}
                      onClick={() => onTest(item.aliasId as string)}
                    >
                      {t("test")}
                    </SmallButton>
                    {own && advanced && item.kind === "chat" ? (
                      <SmallButton
                        disabled={!canManage}
                        label={t("optionsNamed", { name: t(`uses.${item.alias}.title`) })}
                        onClick={() => onOptions(item.aliasId as string)}
                      >
                        {t("options")}
                      </SmallButton>
                    ) : null}
                    {own ? (
                      <SmallButton
                        disabled={!canManage}
                        label={t("clearNamed", { name: t(`uses.${item.alias}.title`) })}
                        onClick={() => onClear(item)}
                      >
                        {t("clear")}
                      </SmallButton>
                    ) : null}
                  </RowActions>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function ProvidersSection({
  providers,
  models,
  canManage,
  advanced,
  tests,
  onTestProvider,
  onEditProvider,
  onRemoveProvider,
  onAddModel,
  onTestModel,
  onEditModel,
  onRemoveModel,
}: {
  providers: Provider[];
  models: Model[];
  canManage: boolean;
  advanced: boolean;
  tests: Tests;
  onTestProvider: (provider: Provider) => void;
  onEditProvider: (provider: Provider) => void;
  onRemoveProvider: (provider: Provider) => void;
  onAddModel: (provider: Provider) => void;
  onTestModel: (model: Model) => void;
  onEditModel: (provider: Provider, model: Model) => void;
  onRemoveModel: (model: Model) => void;
}) {
  const t = useTranslations("models");
  return (
    <section aria-labelledby="models-providers" className="mb-10">
      <h2 className="text-base font-semibold" id="models-providers">
        {t("providers")}
      </h2>
      <p className="mb-4 mt-1 max-w-2xl text-sm leading-relaxed text-[var(--muted-foreground)]">
        {t("providersBody")}
      </p>
      {providers.length === 0 ? <EmptyState title={t("empty")} /> : null}
      <ul className="grid gap-4">
        {providers.map((provider) => {
          const owned = models.filter((model) => model.providerId === provider.id);
          const editable = canManage && !provider.platform;
          return (
            <li className={CARD} key={provider.id}>
              <div className="flex flex-wrap items-start gap-3 p-4">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-sm font-semibold">{provider.name}</h3>

                    {provider.platform ? <Badge>{t("platform")}</Badge> : null}
                    <Badge>{provider.hasApiKey ? t("keyStored") : t("noKey")}</Badge>
                    {advanced ? (
                      <Badge>
                        {t.has(`providerKinds.${provider.kind}`)
                          ? t(`providerKinds.${provider.kind}`)
                          : provider.kind}
                      </Badge>
                    ) : null}
                  </div>
                  <p className="mt-1 break-all text-sm text-[var(--muted-foreground)]">
                    {provider.baseUrl}
                  </p>
                  <TestLine result={tests[`provider:${provider.id}`]} />
                </div>
                <RowActions>
                  <SmallButton
                    disabled={!canManage}
                    label={t("testNamed", { name: provider.name })}
                    onClick={() => onTestProvider(provider)}
                  >
                    {t("test")}
                  </SmallButton>
                  {editable ? (
                    <>
                      <SmallButton
                        label={t("editNamed", { name: provider.name })}
                        onClick={() => onEditProvider(provider)}
                      >
                        {t("edit")}
                      </SmallButton>
                      <SmallButton
                        label={t("removeNamed", { name: provider.name })}
                        onClick={() => onRemoveProvider(provider)}
                      >
                        {t("remove")}
                      </SmallButton>
                    </>
                  ) : null}
                </RowActions>
              </div>
              <ul className="divide-y divide-[var(--border)] border-t border-[var(--border)]">
                {owned.length === 0 ? (
                  <li className="px-4 py-3 text-sm text-[var(--muted-foreground)]">
                    {t("noModels")}
                  </li>
                ) : null}
                {owned.map((model) => (
                  <li className="flex flex-wrap items-start gap-3 px-4 py-3" key={model.id}>
                    <div className="min-w-0 flex-1">
                      <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
                        {model.name}
                        <Badge>{t(`kinds.${model.kind}`)}</Badge>
                        {(model.capabilities ?? []).includes("vision") ? (
                          <Badge>{t("readsImages")}</Badge>
                        ) : null}
                        {model.embeddingDimensions ? (
                          <Badge>
                            {t("dimensionsBadge", { count: model.embeddingDimensions })}
                          </Badge>
                        ) : null}
                      </p>
                      <p className="mt-1 break-all text-xs text-[var(--muted-foreground)]">
                        {model.upstreamModel}
                      </p>
                      <TestLine result={tests[`model:${model.id}`]} />
                    </div>
                    <RowActions>
                      <SmallButton
                        disabled={!canManage}
                        label={t("testNamed", { name: model.name })}
                        onClick={() => onTestModel(model)}
                      >
                        {t("test")}
                      </SmallButton>
                      {editable ? (
                        <>
                          <SmallButton
                            label={t("editNamed", { name: model.name })}
                            onClick={() => onEditModel(provider, model)}
                          >
                            {t("edit")}
                          </SmallButton>
                          <SmallButton
                            label={t("removeNamed", { name: model.name })}
                            onClick={() => onRemoveModel(model)}
                          >
                            {t("remove")}
                          </SmallButton>
                        </>
                      ) : null}
                    </RowActions>
                  </li>
                ))}
              </ul>
              {editable ? (
                <div className="border-t border-[var(--border)] p-3">
                  <SmallButton
                    label={t("addModelNamed", { provider: provider.name })}
                    onClick={() => onAddModel(provider)}
                  >
                    {t("addModel")}
                  </SmallButton>
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** Aliases the tenant added beside the ones the product uses. */
export function AliasesSection({
  aliases,
  models,
  canManage,
  tests,
  onAdd,
  onEdit,
  onTest,
  onRemove,
}: {
  aliases: Alias[];
  models: Model[];
  canManage: boolean;
  tests: Tests;
  onAdd: () => void;
  onEdit: (alias: Alias) => void;
  onTest: (alias: Alias) => void;
  onRemove: (alias: Alias) => void;
}) {
  const t = useTranslations("models");
  const nameOf = (id: string) => models.find((model) => model.id === id)?.name ?? t("modelGone");
  return (
    <section aria-labelledby="models-aliases" className="mb-10">
      <h2 className="text-base font-semibold" id="models-aliases">
        {t("aliasesTitle")}
      </h2>
      <p className="mb-4 mt-1 max-w-2xl text-sm leading-relaxed text-[var(--muted-foreground)]">
        {t("aliasesBody")}
      </p>
      <ul className={`${CARD} divide-y divide-[var(--border)]`}>
        {aliases.length === 0 ? (
          <li className="px-4 py-3 text-sm text-[var(--muted-foreground)]">{t("noAliases")}</li>
        ) : null}
        {aliases.map((alias) => (
          <li className="flex flex-wrap items-start gap-3 px-4 py-3" key={alias.id}>
            <div className="min-w-0 flex-1">
              <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
                <code>{alias.alias}</code>
                <Badge>{t(`kinds.${alias.kind}`)}</Badge>
                {alias.platform ? <Badge>{t("platform")}</Badge> : null}
              </p>
              <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                {nameOf(alias.primaryModelId)}
              </p>
              <TestLine result={tests[`alias:${alias.id}`]} />
            </div>
            <RowActions>
              <SmallButton
                disabled={!canManage}
                label={t("testNamed", { name: alias.alias })}
                onClick={() => onTest(alias)}
              >
                {t("test")}
              </SmallButton>
              {canManage && !alias.platform ? (
                <>
                  <SmallButton
                    label={t("editNamed", { name: alias.alias })}
                    onClick={() => onEdit(alias)}
                  >
                    {t("edit")}
                  </SmallButton>
                  <SmallButton
                    label={t("removeNamed", { name: alias.alias })}
                    onClick={() => onRemove(alias)}
                  >
                    {t("remove")}
                  </SmallButton>
                </>
              ) : null}
            </RowActions>
          </li>
        ))}
      </ul>
      {canManage ? (
        <div className="mt-3">
          <SmallButton onClick={onAdd}>{t("addAlias")}</SmallButton>
        </div>
      ) : null}
    </section>
  );
}
