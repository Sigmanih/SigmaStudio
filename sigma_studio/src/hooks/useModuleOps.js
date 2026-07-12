import { useState } from 'react';

export function useModuleOps({ createModule, updateModule, deleteModule, handleFileDelete }) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingModule, setEditingModule] = useState(null);

  const handleCreateModule = async (data) => {
    const ok = await createModule(data);
    if (ok) setIsModalOpen(false);
  };

  const handleUpdateModule = async (data) => {
    const ok = await updateModule(data, editingModule);
    if (ok) {
      setIsModalOpen(false);
      setEditingModule(null);
    }
  };

  const handleDeleteModule = async (folder) => {
    if (!confirm(`Sei sicuro di voler eliminare il modulo ${folder}?`)) return;
    const ok = await deleteModule(folder);
    if (ok && handleFileDelete) {
      handleFileDelete(`module-${folder}`);
    }
  };

  return {
    isModalOpen,
    setIsModalOpen,
    editingModule,
    setEditingModule,
    handleCreateModule,
    handleUpdateModule,
    handleDeleteModule
  };
}
