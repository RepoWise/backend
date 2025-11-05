"""
Graph Data Loader for Social-Technical Network Analysis

Provides in-memory graph operations using pandas and networkx
WITHOUT requiring Neo4j database.

Loads commit-file-developer relationships from OSSPREY scraper CSV data.
"""
import pandas as pd
import networkx as nx
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from loguru import logger
from collections import defaultdict


class GraphDataLoader:
    """
    Loads and queries developer collaboration graph from CSV data

    Supports queries:
    - Developer → Files (what files did developer X work on?)
    - File → Developers (who worked on file Y?)
    - Developer → Developer (collaboration network)
    - File → File (file coupling through shared developers)
    - Network metrics (centrality, clustering, etc.)
    """

    def __init__(self, csv_path: Optional[str] = None):
        """Initialize graph loader with CSV data path"""
        self.csv_path = csv_path
        self.df: Optional[pd.DataFrame] = None
        self.dev_graph: Optional[nx.Graph] = None
        self.file_graph: Optional[nx.Graph] = None
        self.bipartite_graph: Optional[nx.Graph] = None

        if csv_path and Path(csv_path).exists():
            self.load_data(csv_path)

    def load_data(self, csv_path: str) -> None:
        """
        Load commit-file-dev CSV data and build graphs

        CSV Columns:
        - project_name
        - incubation_start, incubation_end, status
        - commit_number, commit_hash
        - author_email, author_name
        - commit_date, commit_timestamp
        - file_path
        - change_type (A/M/D)
        - lines_added, lines_deleted
        """
        logger.info(f"Loading graph data from: {csv_path}")

        try:
            # Load CSV with proper column names
            self.df = pd.read_csv(
                csv_path,
                names=[
                    "project_name", "incubation_start", "incubation_end", "status",
                    "commit_number", "commit_hash", "author_email", "author_name",
                    "commit_date", "commit_timestamp", "file_path", "change_type",
                    "lines_added", "lines_deleted"
                ],
                header=None  # No header row in CSV
            )

            logger.success(f"Loaded {len(self.df)} commit-file-dev records")

            # Build graphs
            self._build_developer_graph()
            self._build_file_graph()
            self._build_bipartite_graph()

        except Exception as e:
            logger.error(f"Failed to load graph data: {e}")
            raise

    def _build_developer_graph(self) -> None:
        """
        Build developer collaboration graph

        Edges: Two developers are connected if they worked on the same file
        Edge weight: Number of files they collaborated on
        """
        if self.df is None:
            return

        self.dev_graph = nx.Graph()

        # Group by file to find collaborations
        file_devs = self.df.groupby("file_path")["author_name"].apply(set).to_dict()

        # Add developer nodes
        all_devs = self.df["author_name"].unique()
        for dev in all_devs:
            dev_data = self.df[self.df["author_name"] == dev].iloc[0]
            self.dev_graph.add_node(
                dev,
                email=dev_data["author_email"],
                commits=len(self.df[self.df["author_name"] == dev])
            )

        # Add edges for collaborations
        collab_weights = defaultdict(int)
        for file_path, devs in file_devs.items():
            devs_list = list(devs)
            # Create edges between all pairs of developers on this file
            for i, dev1 in enumerate(devs_list):
                for dev2 in devs_list[i+1:]:
                    pair = tuple(sorted([dev1, dev2]))
                    collab_weights[pair] += 1

        # Add weighted edges
        for (dev1, dev2), weight in collab_weights.items():
            self.dev_graph.add_edge(dev1, dev2, weight=weight, files=weight)

        logger.success(
            f"Developer graph: {self.dev_graph.number_of_nodes()} devs, "
            f"{self.dev_graph.number_of_edges()} collaborations"
        )

    def _build_file_graph(self) -> None:
        """
        Build file coupling graph

        Edges: Two files are connected if same developer worked on both
        Edge weight: Number of developers who worked on both files
        """
        if self.df is None:
            return

        self.file_graph = nx.Graph()

        # Group by developer to find file couplings
        dev_files = self.df.groupby("author_name")["file_path"].apply(set).to_dict()

        # Add file nodes
        all_files = self.df["file_path"].unique()
        for file in all_files:
            file_data = self.df[self.df["file_path"] == file]
            self.file_graph.add_node(
                file,
                developers=len(file_data["author_name"].unique()),
                commits=len(file_data),
                total_changes=file_data["lines_added"].sum() + file_data["lines_deleted"].sum()
            )

        # Add edges for couplings
        coupling_weights = defaultdict(int)
        for dev, files in dev_files.items():
            files_list = list(files)
            # Create edges between all pairs of files touched by this dev
            for i, file1 in enumerate(files_list):
                for file2 in files_list[i+1:]:
                    pair = tuple(sorted([file1, file2]))
                    coupling_weights[pair] += 1

        # Add weighted edges
        for (file1, file2), weight in coupling_weights.items():
            self.file_graph.add_edge(file1, file2, weight=weight, developers=weight)

        logger.success(
            f"File graph: {self.file_graph.number_of_nodes()} files, "
            f"{self.file_graph.number_of_edges()} couplings"
        )

    def _build_bipartite_graph(self) -> None:
        """
        Build bipartite graph: developers <-> files

        Edge weight: Number of commits developer made to file
        """
        if self.df is None:
            return

        self.bipartite_graph = nx.Graph()

        # Add developer nodes (set 0)
        all_devs = self.df["author_name"].unique()
        for dev in all_devs:
            self.bipartite_graph.add_node(dev, bipartite=0, type="developer")

        # Add file nodes (set 1)
        all_files = self.df["file_path"].unique()
        for file in all_files:
            self.bipartite_graph.add_node(file, bipartite=1, type="file")

        # Add edges with commit counts
        dev_file_commits = self.df.groupby(["author_name", "file_path"]).size().to_dict()
        for (dev, file), commits in dev_file_commits.items():
            self.bipartite_graph.add_edge(dev, file, weight=commits, commits=commits)

        logger.success(
            f"Bipartite graph: {self.bipartite_graph.number_of_nodes()} nodes, "
            f"{self.bipartite_graph.number_of_edges()} dev-file edges"
        )

    def query_developer_files(self, developer_name: str, limit: int = 20) -> List[Dict]:
        """Get files a developer worked on, sorted by commits"""
        if self.df is None:
            return []

        dev_files = self.df[self.df["author_name"].str.contains(developer_name, case=False, na=False)]

        # Aggregate by file
        file_stats = dev_files.groupby("file_path").agg({
            "commit_hash": "count",
            "lines_added": "sum",
            "lines_deleted": "sum"
        }).rename(columns={"commit_hash": "commits"})

        file_stats = file_stats.sort_values("commits", ascending=False).head(limit)

        results = []
        for file_path, row in file_stats.iterrows():
            results.append({
                "file": file_path,
                "commits": int(row["commits"]),
                "lines_added": int(row["lines_added"]),
                "lines_deleted": int(row["lines_deleted"]),
                "total_changes": int(row["lines_added"] + row["lines_deleted"])
            })

        return results

    def query_file_developers(self, file_pattern: str, limit: int = 20) -> List[Dict]:
        """Get developers who worked on a file (pattern match)"""
        if self.df is None:
            return []

        file_devs = self.df[self.df["file_path"].str.contains(file_pattern, case=False, na=False)]

        # Aggregate by developer
        dev_stats = file_devs.groupby("author_name").agg({
            "commit_hash": "count",
            "lines_added": "sum",
            "lines_deleted": "sum",
            "author_email": "first"
        }).rename(columns={"commit_hash": "commits"})

        dev_stats = dev_stats.sort_values("commits", ascending=False).head(limit)

        results = []
        for dev_name, row in dev_stats.iterrows():
            results.append({
                "developer": dev_name,
                "email": row["author_email"],
                "commits": int(row["commits"]),
                "lines_added": int(row["lines_added"]),
                "lines_deleted": int(row["lines_deleted"]),
                "total_changes": int(row["lines_added"] + row["lines_deleted"])
            })

        return results

    def query_developer_collaborators(self, developer_name: str, limit: int = 10) -> List[Dict]:
        """Get developers who collaborated with given developer"""
        if self.dev_graph is None:
            return []

        # Find matching developer
        matching_devs = [d for d in self.dev_graph.nodes()
                        if developer_name.lower() in d.lower()]

        if not matching_devs:
            return []

        dev = matching_devs[0]

        # Get neighbors (collaborators)
        if dev not in self.dev_graph:
            return []

        collaborators = []
        for neighbor in self.dev_graph.neighbors(dev):
            edge_data = self.dev_graph.get_edge_data(dev, neighbor)
            collaborators.append({
                "developer": neighbor,
                "email": self.dev_graph.nodes[neighbor].get("email", ""),
                "shared_files": edge_data.get("files", 0),
                "total_commits": self.dev_graph.nodes[neighbor].get("commits", 0)
            })

        # Sort by shared files
        collaborators.sort(key=lambda x: x["shared_files"], reverse=True)

        return collaborators[:limit]

    def get_network_stats(self) -> Dict:
        """Get overall network statistics"""
        if not all([self.df is not None, self.dev_graph, self.file_graph]):
            return {}

        return {
            "total_commits": len(self.df),
            "total_developers": len(self.df["author_name"].unique()),
            "total_files": len(self.df["file_path"].unique()),
            "developer_network": {
                "nodes": self.dev_graph.number_of_nodes(),
                "edges": self.dev_graph.number_of_edges(),
                "density": nx.density(self.dev_graph),
                "components": nx.number_connected_components(self.dev_graph)
            },
            "file_network": {
                "nodes": self.file_graph.number_of_nodes(),
                "edges": self.file_graph.number_of_edges(),
                "density": nx.density(self.file_graph)
            },
            "top_developers": self._get_top_developers(5),
            "top_files": self._get_top_files(5)
        }

    def _get_top_developers(self, n: int = 5) -> List[Dict]:
        """Get top N developers by commits"""
        if self.df is None:
            return []

        top_devs = self.df.groupby("author_name").size().sort_values(ascending=False).head(n)

        return [
            {"developer": dev, "commits": int(commits)}
            for dev, commits in top_devs.items()
        ]

    def _get_top_files(self, n: int = 5) -> List[Dict]:
        """Get top N files by developer count"""
        if self.df is None:
            return []

        top_files = (
            self.df.groupby("file_path")["author_name"]
            .nunique()
            .sort_values(ascending=False)
            .head(n)
        )

        return [
            {"file": file, "developers": int(count)}
            for file, count in top_files.items()
        ]


# Multi-project graph storage
_project_graphs: Dict[str, GraphDataLoader] = {}


def get_graph_loader(project_id: Optional[str] = None) -> GraphDataLoader:
    """
    Get or create graph loader instance for a project

    Args:
        project_id: Project identifier (e.g., "owner-repo")
                   If None, returns a demo loader for backward compatibility

    Returns:
        GraphDataLoader instance for the project
    """
    global _project_graphs

    # Backward compatibility: if no project_id, return demo loader
    if project_id is None:
        if "demo" not in _project_graphs:
            # Demo data path
            demo_csv = Path(__file__).parent.parent.parent / \
                       "OSPREY" / "OSSPREY-OSS-Scraper-Tool" / "test" / "test1" / \
                       "Hama-commit-file-dev.csv"

            # Try absolute path from user's system
            if not demo_csv.exists():
                demo_csv = Path("/Users/sankalpkashyap/Desktop/UCD/Research/DECALLab/OSPREY/OSSPREY-OSS-Scraper-Tool/test/test1/Hama-commit-file-dev.csv")

            if demo_csv.exists():
                _project_graphs["demo"] = GraphDataLoader(str(demo_csv))
                logger.info("Loaded demo graph data (Apache Hama)")
            else:
                logger.warning("Demo graph data not found, creating empty loader")
                _project_graphs["demo"] = GraphDataLoader()

        return _project_graphs["demo"]

    # Return existing project graph or create empty one
    if project_id not in _project_graphs:
        logger.info(f"Creating empty graph loader for project: {project_id}")
        _project_graphs[project_id] = GraphDataLoader()

    return _project_graphs[project_id]


def load_project_graph(project_id: str, csv_path: str) -> GraphDataLoader:
    """
    Load graph data for a specific project from CSV

    Args:
        project_id: Unique project identifier
        csv_path: Path to commit-file-dev.csv

    Returns:
        GraphDataLoader instance with loaded data
    """
    global _project_graphs

    if not Path(csv_path).exists():
        logger.error(f"Graph CSV not found: {csv_path}")
        raise FileNotFoundError(f"Graph data CSV not found: {csv_path}")

    logger.info(f"Loading graph data for {project_id} from {csv_path}")

    # Create new loader with CSV data
    loader = GraphDataLoader(csv_path=str(csv_path))

    # Store in project graphs
    _project_graphs[project_id] = loader

    logger.success(f"Loaded graph for {project_id}: {loader.get_network_stats()}")

    return loader


def get_all_project_graphs() -> Dict[str, GraphDataLoader]:
    """Get all loaded project graphs"""
    return _project_graphs.copy()
