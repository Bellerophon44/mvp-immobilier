type ActionGroupProps = {
  title: string;
  items: string[];
  emptyLabel: string;
};

function ActionGroup({ title, items, emptyLabel }: ActionGroupProps) {
  return (
    <div className="action-group">
      <h4 className="action-group-title">
        <span className="action-group-dot" aria-hidden />
        {title}
      </h4>
      {items.length === 0 ? (
        <p className="action-empty">{emptyLabel}</p>
      ) : (
        <ul className="action-list">
          {items.map((item) => (
            <li key={item} className="action-item">
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function Actions({ actions }: any) {
  return (
    <div className="actions-card">
      <h3 className="actions-title">Vos prochaines étapes</h3>
      <p className="actions-subtitle">
        Avant de vous engager, voici sur quoi appuyer.
      </p>

      <ActionGroup
        title="À vérifier avant de visiter"
        items={actions.check || []}
        emptyLabel="Rien de spécifique à signaler."
      />
      <ActionGroup
        title="Questions à poser au vendeur"
        items={actions.questions || []}
        emptyLabel="Aucune question prioritaire."
      />
      <ActionGroup
        title="Arguments pour négocier"
        items={actions.negotiation || []}
        emptyLabel="Aucun levier identifié."
      />
    </div>
  );
}
